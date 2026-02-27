from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Optional
import zipfile
from urllib.parse import quote

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from mortgage_agent.calculator import LoanParams, Prepayment, ScheduleRow, build_schedule, monthly_rate, normalize_method, simulate
from mortgage_agent.report import generate_pdf


app = FastAPI(
    title="息策 Agent",
    description="不只是计算器，是帮你省下一辆车的房贷管家。",
    version="0.1.0",
)


class LoanRequest(BaseModel):
    # 基础贷款信息
    principal: float = Field(..., gt=0, description="贷款总额/本金（元）")
    annual_rate: float = Field(..., ge=0, description="年利率百分比，例如 3.5")
    term_months: int = Field(..., gt=0, description="贷款总期数（月），例如 360")
    method: str = Field(..., description="还款方式：equal_payment(等额本息) / equal_principal(等额本金)")

    # 已还信息（二选一：paid_periods 或 first_payment_date）
    paid_periods: Optional[int] = Field(0, ge=0, description="已还期数（月）。如传 None 则使用 first_payment_date 推算")
    first_payment_date: Optional[date] = Field(None, description="首次还款日期，用于推算已还期数")

    # 提前还款意向
    prepay_amount: float = Field(..., ge=0, description="本次计划提前还款金额（元）")

    # 可选参数
    invest_annual_rate: Optional[float] = Field(None, ge=0, description="可选：理财年化收益率百分比")


class CalcResponse(BaseModel):
    # 仅返回：缩短年限方案 & 减少月供方案的节省利息
    savings_shorten_interest: float
    savings_reduce_payment_interest: float


class CombinedLoanRequest(BaseModel):
    fund_principal: float = Field(..., ge=0, description="公积金贷款本金（元）；0 表示无公积金贷款")
    fund_annual_rate: float = Field(..., ge=0, description="公积金贷款年利率（%）")
    commercial_principal: float = Field(..., ge=0, description="商业贷款本金（元）；0 表示无商业贷款")
    commercial_annual_rate: float = Field(..., ge=0, description="商业贷款年利率（%）")
    term_months: int = Field(..., gt=0, description="贷款总期数（月）")
    method: str = Field("equal_payment", description="还款方式：equal_payment(等额本息) / equal_principal(等额本金)")


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}


@app.post(
    "/v1/mortgages/prepayment:calc",
    tags=["mortgage"],
    responses={400: {"description": "Invalid loan or prepayment parameters"}},
)
def calc_prepayment(body: LoanRequest) -> CalcResponse:
    try:
        params = LoanParams(
            principal=body.principal,
            annual_rate=body.annual_rate,
            term_months=body.term_months,
            method=body.method,
            paid_periods=body.paid_periods,  # 允许 None
            first_payment_date=body.first_payment_date,
        )
        prepay = Prepayment(amount=body.prepay_amount, invest_annual_rate=body.invest_annual_rate)
        result = simulate(params, prepay)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return CalcResponse(
        savings_shorten_interest=float(result.savings_shorten),
        savings_reduce_payment_interest=float(result.savings_reduce),
    )

@app.post(
    "/v1/mortgages/prepayment:export-zip",
    tags=["mortgage"],
    responses={400: {"description": "Invalid loan or prepayment parameters"}},
)
def export_zip(body: LoanRequest):
    """导出还款明细 ZIP（原方案/减少月供/缩短年限，各一份 Excel）。"""
    try:
        params = LoanParams(
            principal=body.principal,
            annual_rate=body.annual_rate,
            term_months=body.term_months,
            method=body.method,
            paid_periods=body.paid_periods,
            first_payment_date=body.first_payment_date,
        )
        prepay = Prepayment(amount=body.prepay_amount, invest_annual_rate=body.invest_annual_rate)
        result = simulate(params, prepay)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    pdf_bytes = generate_pdf(
        result=result,
        prepayment=prepay,
        original_principal=body.principal,
        original_annual_rate=body.annual_rate,
        original_term_months=body.term_months,
        original_method=body.method,
    )

    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("原方案月供明细.xlsx", _schedule_to_xlsx(result.base_schedule))
        zf.writestr("提前还款-减少月供-月供明细.xlsx", _schedule_to_xlsx(result.reduced_schedule))
        zf.writestr("提前还款-缩短年限-月供明细.xlsx", _schedule_to_xlsx(result.shorten_schedule))
        zf.writestr("提前还款-分析报告.pdf", pdf_bytes)
    zip_buf.seek(0)

    return StreamingResponse(
        zip_buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=repayment_schedules.zip",
            "X-Savings-Reduce": f"{float(result.savings_reduce):.2f}",
            "X-Savings-Shorten": f"{float(result.savings_shorten):.2f}",
        },
    )

@app.post(
    "/v1/mortgages/combined:export-xlsx",
    tags=["mortgage"],
    responses={400: {"description": "Invalid loan parameters"}},
)
def export_combined_schedule(body: CombinedLoanRequest):
    """组合贷（公积金 + 商贷）还款计划导出 Excel，响应头返回总利息。"""
    if body.fund_principal <= 0 and body.commercial_principal <= 0:
        raise HTTPException(status_code=400, detail="fund_principal 与 commercial_principal 不能同时为 0")

    try:
        method = normalize_method(body.method)
        fund_schedule = build_schedule(
            body.fund_principal,
            monthly_rate(body.fund_annual_rate),
            body.term_months,
            method,
        )
        commercial_schedule = build_schedule(
            body.commercial_principal,
            monthly_rate(body.commercial_annual_rate),
            body.term_months,
            method,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    max_len = max(len(fund_schedule), len(commercial_schedule))
    combined: list[ScheduleRow] = []
    total_interest = 0.0

    for idx in range(max_len):
        fund = fund_schedule[idx] if idx < len(fund_schedule) else ScheduleRow(idx + 1, 0, 0, 0, 0)
        commercial = commercial_schedule[idx] if idx < len(commercial_schedule) else ScheduleRow(idx + 1, 0, 0, 0, 0)
        payment = fund.payment + commercial.payment
        principal = fund.principal + commercial.principal
        interest = fund.interest + commercial.interest
        balance = fund.balance + commercial.balance
        combined.append(ScheduleRow(idx + 1, payment, principal, interest, balance))
        total_interest += interest

    xlsx_bytes = _combined_schedule_to_xlsx(
        combined,
        commercial_schedule,
        fund_schedule,
        include_commercial=body.commercial_principal > 0,
        include_fund=body.fund_principal > 0,
    )
    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("房贷月供明细.xlsx", xlsx_bytes)
    zip_buf.seek(0)

    return StreamingResponse(
        zip_buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=loan_schedules.zip; "
            f"filename*=UTF-8''{quote('房贷月供明细.zip')}",
            "X-Total-Interest": f"{float(total_interest):.2f}",
        },
    )

def _schedule_to_xlsx(schedule) -> bytes:
    """将还款计划列表导出为 Excel（xlsx），返回二进制。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Schedule"

    headers = ["期数", "月供", "本金", "利息", "余额", "利息占比"]
    ws.append(headers)

    header_font = Font(bold=True, name="Arial", size=11, color="FFFFFF")
    body_font = Font(name="Arial", size=10)
    header_fill = PatternFill("solid", fgColor="0F172A")
    alt_fill = PatternFill("solid", fgColor="F8FAFC")
    border = Border(bottom=Side(style="thin", color="E2E8F0"))
    align_right = Alignment(horizontal="right")
    align_center = Alignment(horizontal="center")

    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align_center

    for idx, row in enumerate(schedule, start=2):
        ratio = (row.interest / row.payment) if row.payment else 0.0
        ws.append([
            row.month_index,
            round(row.payment, 2),
            round(row.principal, 2),
            round(row.interest, 2),
            round(row.balance, 2),
            f"{ratio*100:.2f}%",
        ])
        for col_idx in range(1, 7):
            cell = ws.cell(row=idx, column=col_idx)
            cell.font = body_font
            cell.alignment = align_right if col_idx > 1 else align_center
            if idx % 2 == 0:
                cell.fill = alt_fill
            cell.border = border
        # 利息占比<50% 标红
        ratio_cell = ws.cell(row=idx, column=6)
        if ratio < 0.5:
            ratio_cell.font = Font(name="Arial", size=10, color="EF4444")

    # 列宽
    widths = [8, 14, 14, 14, 16, 12]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def _combined_schedule_to_xlsx(
    combined: list[ScheduleRow],
    commercial_schedule: list[ScheduleRow],
    fund_schedule: list[ScheduleRow],
    include_commercial: bool,
    include_fund: bool,
) -> bytes:
    """组合贷专用：动态输出商贷/公积金列，含各自利息占比与总利息占比。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Combined"

    headers = ["期数", "月供总额"]
    if include_commercial:
        headers += [
            "商贷月供总额",
            "商贷本金",
            "商贷利息",
            "商贷余额",
            "商贷利息占比",
        ]
    if include_fund:
        headers += [
            "公积金月供总额",
            "公积金本金",
            "公积金利息",
            "公积金余额",
            "公积金利息占比",
        ]
    headers.append("利息总占比")
    ws.append(headers)

    header_font = Font(bold=True, name="Arial", size=11, color="FFFFFF")
    body_font = Font(name="Arial", size=10)
    header_fill_base = PatternFill("solid", fgColor="0F172A")
    header_fill_commercial = PatternFill("solid", fgColor="1D4ED8")
    header_fill_fund = PatternFill("solid", fgColor="047857")
    body_fill_commercial = PatternFill("solid", fgColor="EFF6FF")
    body_fill_fund = PatternFill("solid", fgColor="ECFDF3")
    alt_fill = PatternFill("solid", fgColor="F8FAFC")
    border = Border(bottom=Side(style="thin", color="E2E8F0"))
    align_right = Alignment(horizontal="right")
    align_center = Alignment(horizontal="center")

    commercial_cols = [idx for idx, h in enumerate(headers, start=1) if h.startswith("商贷")]
    fund_cols = [idx for idx, h in enumerate(headers, start=1) if h.startswith("公积金")]

    for idx, cell in enumerate(ws[1], start=1):
        cell.font = header_font
        if idx in commercial_cols:
            cell.fill = header_fill_commercial
        elif idx in fund_cols:
            cell.fill = header_fill_fund
        else:
            cell.fill = header_fill_base
        cell.alignment = align_center

    max_len = len(combined)
    for idx in range(max_len):
        combined_row = combined[idx]
        row_values = [
            combined_row.month_index,
            round(combined_row.payment, 2),
        ]

        if include_commercial:
            c = commercial_schedule[idx] if idx < len(commercial_schedule) else ScheduleRow(idx + 1, 0, 0, 0, 0)
            c_ratio = (c.interest / c.payment * 100) if c.payment else 0.0
            row_values += [
                round(c.payment, 2),
                round(c.principal, 2),
                round(c.interest, 2),
                round(c.balance, 2),
                f"{c_ratio:.2f}%",
            ]

        if include_fund:
            f = fund_schedule[idx] if idx < len(fund_schedule) else ScheduleRow(idx + 1, 0, 0, 0, 0)
            f_ratio = (f.interest / f.payment * 100) if f.payment else 0.0
            row_values += [
                round(f.payment, 2),
                round(f.principal, 2),
                round(f.interest, 2),
                round(f.balance, 2),
                f"{f_ratio:.2f}%",
            ]

        total_ratio = (combined_row.interest / combined_row.payment * 100) if combined_row.payment else 0.0
        row_values.append(f"{total_ratio:.2f}%")

        ws.append(row_values)

        for col_idx in range(1, len(row_values) + 1):
            cell = ws.cell(row=idx + 2, column=col_idx)
            cell.font = body_font
            cell.alignment = align_right if col_idx > 1 else align_center
            if col_idx in commercial_cols:
                cell.fill = body_fill_commercial
            elif col_idx in fund_cols:
                cell.fill = body_fill_fund
            elif (idx + 2) % 2 == 0:
                cell.fill = alt_fill
            cell.border = border

    for i in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 14

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()

