"""息策 Agent（房贷提前还款分析）Python 包。

常用导入：
    from mortgage_agent import LoanParams, Prepayment, simulate

调试运行：
    python -m mortgage_agent

该调试入口会：
1) 跑一组示例 simulate
2) 生成一份示例 PDF 到 output/ 目录
"""

from .calculator import LoanParams, Prepayment, SimulationResult, ScheduleRow, simulate

__all__ = [
    "LoanParams",
    "Prepayment",
    "SimulationResult",
    "ScheduleRow",
    "simulate",
]


