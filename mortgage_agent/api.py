from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Optional
import zipfile

import openpyxl
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from mortgage_agent.calculator import LoanParams, Prepayment, simulate
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


@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/mortgages/prepayment:calc", response_model=CalcResponse, tags=["mortgage"])
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

@app.post("/v1/mortgages/prepayment:export-zip", tags=["mortgage"])
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

    # 生成 PDF 报告并写入 ZIP
    pdf_path = generate_pdf(
        result=result,
        prepayment=prepay,
        output_dir="output",
        original_principal=body.principal,
        original_annual_rate=body.annual_rate,
        original_term_months=body.term_months,
        original_method=body.method,
    )

    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("原方案.xlsx", _schedule_to_xlsx(result.base_schedule))
        zf.writestr("减少月供.xlsx", _schedule_to_xlsx(result.reduced_schedule))
        zf.writestr("缩短年限.xlsx", _schedule_to_xlsx(result.shorten_schedule))
        with open(pdf_path, "rb") as f:
            zf.writestr("报告.pdf", f.read())
    zip_buf.seek(0)

    return StreamingResponse(
        zip_buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=repayment_schedules.zip"},
    )

def _schedule_to_xlsx(schedule) -> bytes:
    """将还款计划列表导出为 Excel（xlsx），返回二进制。"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Schedule"

    headers = ["期数", "月供", "本金", "利息", "余额", "利息占比"]
    ws.append(headers)

    header_font = openpyxl.styles.Font(bold=True, name="Arial", size=11, color="FFFFFF")
    body_font = openpyxl.styles.Font(name="Arial", size=10)
    header_fill = openpyxl.styles.PatternFill("solid", fgColor="0F172A")
    alt_fill = openpyxl.styles.PatternFill("solid", fgColor="F8FAFC")
    border = openpyxl.styles.Border(
        bottom=openpyxl.styles.Side(style="thin", color="E2E8F0")
    )
    align_right = openpyxl.styles.Alignment(horizontal="right")
    align_center = openpyxl.styles.Alignment(horizontal="center")

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
            ratio_cell.font = openpyxl.styles.Font(name="Arial", size=10, color="EF4444")

    # 列宽
    widths = [8, 14, 14, 14, 16, 12]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()
