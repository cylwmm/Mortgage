from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple
import math


# 还款方式常量：等额本息 / 等额本金
METHOD_ANNUITY = "equal_payment"
METHOD_EQUAL_PRINCIPAL = "equal_principal"


@dataclass
class LoanParams:
    """贷款输入参数。

    字段说明：
        principal: 贷款总额/贷款本金（单位：元）。
        annual_rate: 年利率（百分比），例如 3.5 表示 3.5%。
        term_months: 贷款总期数（月），例如 360。
        method: 还款方式（支持：equal_payment/annuity 等额本息；equal_principal 等额本金）。
        paid_periods: 已还期数（月）。如果不填/填 None，可通过 first_payment_date 推算。
        first_payment_date: 首次还款日期（用于自动推算已还期数）。
    """

    principal: float
    annual_rate: float
    term_months: int
    method: str
    paid_periods: int = 0
    first_payment_date: Optional[date] = None


@dataclass
class Prepayment:
    """提前还款相关输入。

    字段说明：
        amount: 本次计划提前还款金额（单位：元）。会自动截断到 <= 剩余本金。
        invest_annual_rate: 可选：理财年化收益率（百分比），用于后续做“还贷 vs 理财”的对比。
    """

    amount: float
    invest_annual_rate: Optional[float] = None


@dataclass
class ScheduleRow:
    """单期（月）还款计划明细。

    字段说明：
        month_index: 期数序号（从 1 开始）。
        payment: 本期实际还款额（单位：元）。
        principal: 本期归还本金（单位：元）。
        interest: 本期支付利息（单位：元）。
        balance: 本期还款后剩余本金余额（单位：元）。
    """

    month_index: int
    payment: float
    principal: float
    interest: float
    balance: float


@dataclass
class SimulationResult:
    """模拟结果汇总（基准 + 两种提前还款方案）。

    字段说明：
        paid_periods: 已还期数。
        remaining_months: 剩余期数（基准方案）。
        remaining_principal: 剩余本金（基准方案）。
        original_monthly_payment: 原月供（基准方案在剩余阶段的月供；等额本金会随期数变化，这里取剩余第一期的月供）。

        reduced_monthly_payment: “减少月供方案”的新月供（同样取该方案剩余第一期的月供）。
        shorten_months: “缩短年限方案”提前还款后剩余需要还的期数（倒推出的月数）。

        base_remaining_interest: 基准方案剩余总利息。
        reduced_remaining_interest: 减少月供方案剩余总利息。
        shorten_remaining_interest: 缩短年限方案剩余总利息。

        savings_reduce: 减少月供方案节省利息 = base_remaining_interest - reduced_remaining_interest。
        savings_shorten: 缩短年限方案节省利息 = base_remaining_interest - shorten_remaining_interest。

        base_schedule: 基准方案的“剩余期”明细表（从 paid_periods+1 期开始）。
        reduced_schedule: 减少月供方案的明细表。
        shorten_schedule: 缩短年限方案的明细表。

        interest_by_year: 基准方案剩余期内：按“贷款年度(第1年、第2年...)”汇总的利息。

        critical_month_index: 临界点（月序号，从剩余期的 1 开始）。用于提示“不建议继续提前还款”的时间点。
        critical_reason: 临界点命中原因（枚举字符串）：
            - monthly_interest_below_principal: 单月利息 < 单月本金
            - remaining_interest_below_10_percent: 剩余总利息/剩余总还款 < 10%
    """

    paid_periods: int
    remaining_months: int
    remaining_principal: float
    original_monthly_payment: float
    reduced_monthly_payment: float
    shorten_months: int
    base_remaining_interest: float
    reduced_remaining_interest: float
    shorten_remaining_interest: float
    savings_reduce: float
    savings_shorten: float
    base_schedule: List[ScheduleRow]
    reduced_schedule: List[ScheduleRow]
    shorten_schedule: List[ScheduleRow]
    interest_by_year: Dict[int, float]
    critical_month_index: Optional[int]
    critical_reason: Optional[str]


def monthly_rate(annual_rate: float) -> float:
    # 年利率百分比 -> 月利率小数。例如 3.6% => 0.003
    return annual_rate / 100.0 / 12.0


def annuity_payment(principal: float, rate: float, months: int) -> float:
    if months <= 0:
        return 0.0
    if rate == 0:
        return principal / months
    factor = math.pow(1 + rate, months)
    return principal * rate * factor / (factor - 1)


def normalize_method(method: str) -> str:
    # 统一并校验还款方式输入，支持一些别名。
    if not method:
        raise ValueError("repayment method is required")
    normalized = method.strip().lower()
    if normalized in ("annuity", "equal_payment", "equal_installment"):
        return METHOD_ANNUITY
    if normalized in ("equal_principal", "principal"):
        return METHOD_EQUAL_PRINCIPAL
    raise ValueError(f"unsupported repayment method: {method}")


def compute_paid_periods(params: LoanParams, today: Optional[date] = None) -> int:
    # 优先使用显式已还期数；否则用首次还款日期推算“已过了多少个月”。
    if params.paid_periods is not None:
        return min(max(params.paid_periods, 0), params.term_months)
    if not params.first_payment_date:
        return 0

    today = today or date.today()
    months = (today.year - params.first_payment_date.year) * 12 + (today.month - params.first_payment_date.month)
    # 若本月尚未到达“还款日”，则认为本月还未完成一期
    if today.day < params.first_payment_date.day:
        months -= 1
    return min(max(months, 0), params.term_months)


def build_schedule(principal: float, rate: float, months: int, method: str) -> List[ScheduleRow]:
    # 生成完整（或剩余）还款计划：支持等额本息 / 等额本金。
    rows: List[ScheduleRow] = []
    balance = principal
    if months <= 0 or principal <= 0:
        return rows

    # 等额本金：每月固定归还本金；利息按剩余本金计算，因此月供逐月递减
    if method == METHOD_EQUAL_PRINCIPAL:
        principal_part = principal / months
        for i in range(1, months + 1):
            interest = balance * rate
            principal_payment = min(principal_part, balance)
            payment = principal_payment + interest
            balance -= principal_payment
            rows.append(ScheduleRow(i, payment, principal_payment, interest, balance))
        return rows

    # 等额本息：月供固定；本金占比逐月上升、利息占比逐月下降
    payment = annuity_payment(principal, rate, months)
    for i in range(1, months + 1):
        interest = balance * rate
        principal_payment = min(payment - interest, balance)
        payment_effective = principal_payment + interest
        balance -= principal_payment
        rows.append(ScheduleRow(i, payment_effective, principal_payment, interest, balance))
    return rows


def build_fixed_payment_schedule(
    principal: float,
    rate: float,
    payment: float,
    max_months: int,
) -> List[ScheduleRow]:
    # “缩短年限方案”：保持月供不变（payment 固定），倒推需要多少期还清（期限可变）。
    rows: List[ScheduleRow] = []
    balance = principal
    if principal <= 0 or payment <= 0:
        return rows

    for i in range(1, max_months + 1):
        interest = balance * rate
        principal_payment = payment - interest
        # 如果连利息都覆盖不了，表示该 monthly payment 不足以还清（理论上不会发生于常规房贷参数）
        if principal_payment <= 0:
            break

        principal_payment = min(principal_payment, balance)
        payment_effective = principal_payment + interest
        balance -= principal_payment
        rows.append(ScheduleRow(i, payment_effective, principal_payment, interest, balance))
        if balance <= 0:
            break
    return rows


def aggregate_interest_by_year(schedule: List[ScheduleRow]) -> Dict[int, float]:
    # 按“贷款年度”汇总利息（第1年=1~12期，第2年=13~24期 ...）。
    totals: Dict[int, float] = {}
    for row in schedule:
        year = (row.month_index - 1) // 12 + 1
        totals[year] = totals.get(year, 0.0) + row.interest
    return totals


def find_critical_point(schedule: List[ScheduleRow]) -> Tuple[Optional[int], Optional[str]]:
    # 临界点：
    # 1) 单月利息 < 单月本金（说明已进入“本金还款期”）
    # 2) 或者剩余总利息 / 剩余总还款 < 10%（说明后续利息占比极低）
    if not schedule:
        return None, None

    # 预先计算“从第 i 期到最后一期”的利息与还款额后缀和，方便 O(n) 判断
    suffix_interest = [0.0] * (len(schedule) + 1)
    suffix_payment = [0.0] * (len(schedule) + 1)
    for i in range(len(schedule) - 1, -1, -1):
        suffix_interest[i] = suffix_interest[i + 1] + schedule[i].interest
        suffix_payment[i] = suffix_payment[i + 1] + schedule[i].payment

    for i, row in enumerate(schedule):
        if row.interest < row.principal:
            return row.month_index, "monthly_interest_below_principal"
        remaining_ratio = suffix_interest[i] / suffix_payment[i] if suffix_payment[i] else 0.0
        if remaining_ratio < 0.10:
            return row.month_index, "remaining_interest_below_10_percent"
    return None, None


def simulate(params: LoanParams, prepayment: Prepayment) -> SimulationResult:
    # 主流程：
    # 1) 先生成基准方案完整还款表，并切出“剩余期”部分
    # 2) 提前还款后得到 new_principal
    # 3) 方案A：减少月供（期限不变）=> 重新按剩余期数摊还
    # 4) 方案B：缩短年限（月供不变）=> 以原月供倒推剩余期数
    if params.principal <= 0 or params.term_months <= 0:
        # 输入不合法时安全返回空结果
        return SimulationResult(
            paid_periods=0,
            remaining_months=0,
            remaining_principal=0.0,
            original_monthly_payment=0.0,
            reduced_monthly_payment=0.0,
            shorten_months=0,
            base_remaining_interest=0.0,
            reduced_remaining_interest=0.0,
            shorten_remaining_interest=0.0,
            savings_reduce=0.0,
            savings_shorten=0.0,
            base_schedule=[],
            reduced_schedule=[],
            shorten_schedule=[],
            interest_by_year={},
            critical_month_index=None,
            critical_reason=None,
        )

    method = normalize_method(params.method)
    rate = monthly_rate(params.annual_rate)
    paid_periods = compute_paid_periods(params)

    base_schedule_full = build_schedule(params.principal, rate, params.term_months, method)
    base_remaining = base_schedule_full[paid_periods:]
    remaining_months = len(base_remaining)

    if paid_periods <= 0:
        remaining_principal = params.principal
    else:
        remaining_principal = base_schedule_full[paid_periods - 1].balance

    original_monthly_payment = base_remaining[0].payment if base_remaining else 0.0

    if remaining_months == 0 or remaining_principal <= 0:
        # 已还清或无剩余
        return SimulationResult(
            paid_periods=paid_periods,
            remaining_months=0,
            remaining_principal=0.0,
            original_monthly_payment=0.0,
            reduced_monthly_payment=0.0,
            shorten_months=0,
            base_remaining_interest=0.0,
            reduced_remaining_interest=0.0,
            shorten_remaining_interest=0.0,
            savings_reduce=0.0,
            savings_shorten=0.0,
            base_schedule=[],
            reduced_schedule=[],
            shorten_schedule=[],
            interest_by_year={},
            critical_month_index=None,
            critical_reason=None,
        )

    # 提前还款金额不可超过剩余本金
    prepay_amount = min(prepayment.amount, remaining_principal)
    new_principal = max(remaining_principal - prepay_amount, 0.0)

    reduced_schedule = build_schedule(new_principal, rate, remaining_months, method)
    reduced_monthly_payment = reduced_schedule[0].payment if reduced_schedule else 0.0

    shorten_schedule = build_fixed_payment_schedule(
        new_principal,
        rate,
        original_monthly_payment,
        max_months=max(remaining_months, 1) * 2,
    )

    # 计算三种方案“剩余总利息”
    base_remaining_interest = sum(row.interest for row in base_remaining)
    reduced_remaining_interest = sum(row.interest for row in reduced_schedule)
    shorten_remaining_interest = sum(row.interest for row in shorten_schedule)

    # 计算节省利息
    savings_reduce = base_remaining_interest - reduced_remaining_interest
    savings_shorten = base_remaining_interest - shorten_remaining_interest

    # 基准方案剩余期：按年度汇总利息 + 临界点分析
    interest_by_year = aggregate_interest_by_year(base_remaining)
    critical_month_index, critical_reason = find_critical_point(base_remaining)

    return SimulationResult(
        paid_periods=paid_periods,
        remaining_months=remaining_months,
        remaining_principal=remaining_principal,
        original_monthly_payment=original_monthly_payment,
        reduced_monthly_payment=reduced_monthly_payment,
        shorten_months=len(shorten_schedule),
        base_remaining_interest=base_remaining_interest,
        reduced_remaining_interest=reduced_remaining_interest,
        shorten_remaining_interest=shorten_remaining_interest,
        savings_reduce=savings_reduce,
        savings_shorten=savings_shorten,
        base_schedule=base_remaining,
        reduced_schedule=reduced_schedule,
        shorten_schedule=shorten_schedule,
        interest_by_year=interest_by_year,
        critical_month_index=critical_month_index,
        critical_reason=critical_reason,
    )

