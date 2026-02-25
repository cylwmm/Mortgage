from __future__ import annotations

import os
import uuid
import tempfile
from datetime import date
from typing import Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Flowable,
)

from mortgage_agent.calculator import Prepayment, SimulationResult


# --- Setup Fonts and Colors ---

FONT_NAME = "STSong-Light"
FONT_NAME_BOLD = "STSong-Light"  # CID 字体使用 <b> 标签加粗
NUM_FONT = "Helvetica"  # 数字/英文使用西文字体，避免拥挤
pdfmetrics.registerFont(UnicodeCIDFont(FONT_NAME))

PALETTE = {
    "primary_text": "#1E293B",
    "secondary_text": "#64748B",
    "accent_green": "#10B981",
    "accent_blue": "#3B82F6",
    "highlight_bg": "#F1F5F9",
    "border": "#E2E8F0",
    "warning": "#EF4444",
    "white": "#FFFFFF",
    "dark_header": "#0F172A",
}


def _method_cn(method: str) -> str:
    """还款方式中文化显示。"""
    m = (method or "").strip().lower()
    if m in ("equal_payment", "annuity", "equal_installment"):
        return "等额本息"
    if m in ("equal_principal", "principal"):
        return "等额本金"
    return method


def _invest_future_value(principal: float, annual_rate_pct: float, years: int) -> float:
    """理财收益（按年复利近似）。"""
    if years <= 0:
        return principal
    r = annual_rate_pct / 100.0
    return principal * ((1.0 + r) ** years)


def _fmt_money(v: float) -> str:
    return f"￥{v:,.2f}"


def _fmt_money_font(v: float) -> str:
    return f"<font name='{FONT_NAME}'>￥</font><font name='{NUM_FONT}'>{v:,.2f}</font>"


def _fmt_percent_font(v: float) -> str:
    return f"<font name='{NUM_FONT}'>{v:.2f}%</font>"


def _months_to_years_months(m: int) -> Tuple[int, int]:
    years = m // 12
    months = m % 12
    return years, months


def _score_label(saved: float, prepay_amount: float) -> str:
    if prepay_amount <= 0:
        return "谨慎执行（资金利用率低）"
    ratio = saved / prepay_amount
    if ratio >= 0.5:
        return "建议执行（省钱效率极高）"
    if ratio >= 0.2:
        return "建议执行（省钱效率较高）"
    if ratio >= 0.1:
        return "可考虑（收益一般）"
    return "谨慎执行（资金利用率低）"


class PageHeader(Flowable):
    """一条水平分割线。"""

    def __init__(self, width, height=0):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self):
        self.canv.setStrokeColor(colors.HexColor(PALETTE["border"]))
        self.canv.setLineWidth(0.4)
        self.canv.line(0, self.height, self.width, self.height)


def _header_footer(canvas, doc):
    """每页页眉页脚。"""
    canvas.saveState()
    header_text = "息策 ▲ 提前还款分析"
    canvas.setFont(FONT_NAME, 9)
    canvas.setFillColor(colors.HexColor(PALETTE["secondary_text"]))
    # 顶部细线 + 抬高标题，避免压正文
    canvas.setStrokeColor(colors.HexColor(PALETTE["border"]))
    canvas.setLineWidth(0.4)
    canvas.line(doc.leftMargin, doc.height + doc.topMargin - 9 * mm, doc.width + doc.leftMargin, doc.height + doc.topMargin - 9 * mm)
    canvas.drawString(doc.leftMargin, doc.height + doc.topMargin - 7 * mm, header_text)

    footer_text = f"生成日期: {date.today().strftime('%Y-%m-%d')}"
    canvas.setFont(FONT_NAME, 8)
    canvas.drawString(doc.leftMargin, 10 * mm, footer_text)
    canvas.drawRightString(doc.width + doc.leftMargin, 10 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def generate_pdf(
    *,
    result: SimulationResult,
    prepayment: Prepayment,
    output_dir: str,
    original_principal: float,
    original_annual_rate: float,
    original_term_months: int,
    original_method: str,
) -> str:
    """根据 simulate 的结果生成 PDF，返回 PDF 文件路径。

    注意：PDF 首页展示的“原贷款信息”应使用用户输入的原始数据（LoanRequest），
    而不是从还款表反推，避免不准确。
    """

    # 允许不传 output_dir，此时生成到系统临时目录
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        pdf_path = os.path.join(output_dir, f"report_{uuid.uuid4().hex}.pdf")
    else:
        tmp = tempfile.NamedTemporaryFile(prefix="report_", suffix=".pdf", delete=False)
        pdf_path = tmp.name
        tmp.close()

    # 基准：剩余期数 & 关键数
    base_remaining_months = result.remaining_months
    shorten_months = result.shorten_months
    shorten_saved = float(result.savings_shorten)
    reduce_saved = float(result.savings_reduce)

    shorten_years, shorten_left_months = _months_to_years_months(base_remaining_months - shorten_months)

    # “核心摘要”主打：选择节省利息更高的方案作为首页大数字
    best_saved = max(shorten_saved, reduce_saved)
    best_label = _score_label(best_saved, float(prepayment.amount))

    # --- Define Styles ---
    styles = getSampleStyleSheet()

    meta_style = ParagraphStyle(
        "meta_cn",
        parent=styles["BodyText"],
        fontName=FONT_NAME,
        fontSize=9.5,
        leading=14.5,
        textColor=colors.HexColor(PALETTE["secondary_text"]),
    )

    base_style = ParagraphStyle(
        "base_cn",
        parent=styles["BodyText"],
        fontName=FONT_NAME,
        fontSize=10.2,
        leading=19,
        wordWrap="CJK",
        textColor=colors.HexColor(PALETTE["primary_text"]),
    )

    title_style = ParagraphStyle(
        "title_cn",
        parent=styles["Title"],
        fontName=FONT_NAME_BOLD,
        fontSize=25,
        leading=33,
        textColor=colors.HexColor(PALETTE["primary_text"]),
        spaceAfter=10,
    )

    h2_style = ParagraphStyle(
        "h2_cn",
        parent=styles["Heading2"],
        fontName=FONT_NAME_BOLD,
        fontSize=16.5,
        leading=23,
        textColor=colors.HexColor(PALETTE["primary_text"]),
        spaceBefore=8,
        spaceAfter=8,
    )

    big_green_style = ParagraphStyle(
        "big_green",
        parent=styles["Title"],
        fontName=NUM_FONT,
        fontSize=40,
        leading=48,
        textColor=colors.HexColor(PALETTE["accent_green"]),
        alignment=1,
        spaceBefore=6,
        spaceAfter=6,
    )

    tag_style = ParagraphStyle(
        "tag",
        parent=styles["BodyText"],
        fontName=FONT_NAME,
        fontSize=12,
        leading=16,
        textColor=colors.HexColor(PALETTE["accent_green"]),
        backColor=colors.HexColor("#ECFDF3"),
        borderPadding=7,
        alignment=1,
        spaceAfter=8,
    )

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=32 * mm,
        bottomMargin=22 * mm,
        title="息策 Agent - 提前还款分析报告",
        author="息策 Agent",
    )

    story = []

    # -------------------- 第 1 页：核心摘要 --------------------
    # 首屏额外留白，确保不与页眉重叠
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("<b>息策 ▲ 提前还款分析</b>", title_style))
    story.append(
        Paragraph(
            "高级决策简报 · 以收益视角评估提前还款价值",
            ParagraphStyle(name="subtitle_cn", parent=base_style, textColor=colors.HexColor(PALETTE["secondary_text"]), fontSize=10.5, leading=16),
        )
    )

    story.append(Paragraph(f"生成日期：{date.today().strftime('%Y-%m-%d')}", meta_style))
    story.append(PageHeader(doc.width))
    story.append(Spacer(1, 6 * mm))

    # 信息卡片：原贷款信息 + 还款进度 + 本次提前还款
    info_style = ParagraphStyle("info_cn", parent=base_style, leading=17)
    info_data = [
        ["原贷款信息", "还款进度", "本次提前还款"],
        [
            Paragraph(
                f"贷款金额：{_fmt_money_font(float(original_principal))}<br/>"
                f"年利率：{_fmt_percent_font(float(original_annual_rate))}<br/>"
                f"贷款期限：{int(original_term_months)} 期<br/>"
                f"还款方式：{_method_cn(original_method)}",
                info_style,
            ),
            Paragraph(
                f"已还期数：{result.paid_periods} 期<br/>"
                f"剩余期数：{result.remaining_months} 期<br/>"
                f"剩余本金：{_fmt_money_font(result.remaining_principal)}<br/>"
                f"当前月供（参考）：{_fmt_money_font(result.original_monthly_payment)}",
                info_style,
            ),
            Paragraph(
                f"提前还款金额：{_fmt_money_font(float(prepayment.amount))}<br/>"
                f"理财年化（可选）：{_fmt_percent_font(float(prepayment.invest_annual_rate)) if prepayment.invest_annual_rate is not None else '未填写'}",
                info_style,
            ),
        ],
    ]

    info_table = Table(info_data, colWidths=[58 * mm, 58 * mm, 54 * mm])
    info_table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), FONT_NAME, 9.7),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PALETTE["highlight_bg"])),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(PALETTE["secondary_text"])),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor(PALETTE["border"])),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(PALETTE["border"])),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor(PALETTE["border"])),
                ("PADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(info_table)

    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("本次还款预计为您节省", ParagraphStyle(name="saving_title_cn", parent=base_style, alignment=1, fontSize=11)))
    story.append(Paragraph(f"{_fmt_money_font(best_saved)}", big_green_style))
    story.append(Paragraph(best_label, tag_style))
    story.append(Spacer(1, 4 * mm))

    story.append(
        Paragraph(
            "* 详细还款明细请查看导出的 <font name='Helvetica'>Excel</font> 文件（含原方案 / 减少月供 / 缩短年限）。",
            ParagraphStyle(
                name="note_excel",
                parent=base_style,
                fontSize=9,
                leading=13,
                textColor=colors.HexColor(PALETTE["secondary_text"]),
            ),
        )
    )

    summary_data = [
        ["方案", "关键变化", "预计节省利息"],
        [
            "缩短年限（推荐）",
            Paragraph(
                f"月供不变，预计提前 {shorten_years} 年 {shorten_left_months} 个月结清",
                base_style,
            ),
            Paragraph(_fmt_money_font(shorten_saved), ParagraphStyle(name="sum_money1", parent=base_style, fontName=NUM_FONT, alignment=2)),
        ],
        [
            "减少月供",
            Paragraph(
                f"期限不变，月供从约 {_fmt_money_font(result.original_monthly_payment)} 降至约 {_fmt_money_font(result.reduced_monthly_payment)}",
                base_style,
            ),
            Paragraph(_fmt_money_font(reduce_saved), ParagraphStyle(name="sum_money2", parent=base_style, fontName=NUM_FONT, alignment=2)),
        ],
    ]

    t = Table(summary_data, colWidths=[45 * mm, 85 * mm, 40 * mm])
    t.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), FONT_NAME, 10.2),
                ("FONT", (2, 1), (2, -1), NUM_FONT, 10.2),  # 金额列使用西文字体
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PALETTE["dark_header"])),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(PALETTE["white"])),
                ("ALIGN", (2, 1), (2, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, 0), 1.5, colors.HexColor(PALETTE["dark_header"])),
                ("LINEBELOW", (0, -1), (-1, -1), 0.8, colors.HexColor(PALETTE["border"])),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFFFFF"), colors.HexColor(PALETTE["highlight_bg"])]),
                ("PADDING", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0, colors.transparent),
            ]
        )
    )
    story.append(Spacer(1, 5 * mm))
    story.append(t)

    if result.critical_month_index:
        idx = result.critical_month_index
        row = result.base_schedule[idx - 1] if 0 < idx <= len(result.base_schedule) else None
        ratio = (row.interest / row.payment) if (row and row.payment > 0) else None

        y, m = _months_to_years_months(idx - 1)
        ratio_text = f"（该期利息占比约 {ratio * 100:.1f}%）" if ratio is not None else ""

        critical_text = (
            f"<b>临界点提示（按原方案）：</b>"
            f"剩余还款从第{idx}期开始（约第{y+1}年第{m+1}个月），"
            f"利息占比显著下降{ratio_text}；此后提前还贷的边际收益可能变低。"
        )

        story.append(Spacer(1, 8))
        story.append(
            Paragraph(
                critical_text,
                ParagraphStyle(
                    name="critical_point_tip",
                    parent=base_style,
                    fontSize=9.6,
                    leading=13.5,
                    backColor=colors.HexColor(PALETTE["highlight_bg"]),
                    borderPadding=8,
                ),
            )
        )

    story.append(PageBreak())

    # -------------------- 第 2 页：理财建议 --------------------
    story.append(Paragraph("理财建议", h2_style))
    story.append(PageHeader(doc.width))

    saved_for_compare = best_saved
    prepay_amount = float(prepayment.amount)

    invest_rate = prepayment.invest_annual_rate
    if invest_rate is None:
        story.append(
            Paragraph(
                "您未提供理财年化收益率，通用建议：当贷款进入“本金还款期”后，提前还款的边际收益下降，"
                "可考虑将资金用于更高收益理财或保留流动性。",
                base_style,
            )
        )
    else:
        years = 20
        fv = _invest_future_value(prepay_amount, float(invest_rate), years)
        invest_gain = fv - prepay_amount
        diff = saved_for_compare - invest_gain

        story.append(
            Paragraph(
                f"<b>理财收益模拟：</b>假设您不提前还款，将 {_fmt_money_font(prepay_amount)} 投入年化 <b>{_fmt_percent_font(float(invest_rate))}</b> 的理财，"
                f"{years} 年后预计收益约 <b>{_fmt_money_font(invest_gain)}</b>。",
                base_style,
            )
        )
        story.append(Spacer(1, 6))
        story.append(
            Paragraph(
                f"<b>还贷节省收益：</b>本次提前还款在最佳方案下预计节省利息约 <b>{_fmt_money_font(saved_for_compare)}</b>。",
                base_style,
            )
        )
        story.append(Spacer(1, 10))

        if diff >= 0:
            story.append(
                Paragraph(
                    f"<b>结论：<font color='{PALETTE['accent_green']}'>还贷比理财多赚约 {_fmt_money_font(diff)}</font></b>。"
                    "<br/><br/>若您追求稳健确定性，且短期内无大额资金需求，建议执行提前还款。",
                    base_style,
                )
            )
        else:
            story.append(
                Paragraph(
                    f"<b>结论：<font color='{PALETTE['accent_blue']}'>理财比还贷多赚约 {_fmt_money_font(-diff)}</font></b>。"
                    "<br/><br/>若您能接受理财市场的波动、且有足够风险承受能力，可谨慎考虑不提前还款，将资金用于收益更高的用途。",
                    base_style,
                )
            )

    story.append(Spacer(1, 12 * mm))
    story.append(PageHeader(doc.width))
    story.append(Spacer(1, 4 * mm))
    story.append(
        Paragraph(
            "<b>免责声明：</b>本报告基于您提供的数据进行数学模拟，结果仅供参考。实际还款规则可能受银行计息方式、扣款日、提前还款手续费等多种因素影响。"
            "如需执行具体操作，请务必以银行出具的官方还款计划表为准。",
            ParagraphStyle(
                "disclaimer",
                parent=base_style,
                fontSize=8.5,
                leading=14,
                textColor=colors.HexColor(PALETTE["secondary_text"]),
            ),
        )
    )

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return pdf_path

