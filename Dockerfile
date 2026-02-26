# 多阶段构建：减小最终镜像大小

# 阶段 1: 构建阶段
FROM python:3.11-slim as builder

WORKDIR /build

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制 requirements.txt 并安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 阶段 2: 运行阶段
FROM python:3.11-slim

WORKDIR /app

# 安装运行时必需的系统包
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制 Python 依赖
COPY --from=builder /root/.local /root/.local

# 设置 PATH
ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 复制应用代码
COPY mortgage_agent/ ./mortgage_agent/
COPY README.md .

# 创建非 root 用户（安全最佳实践）
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# 默认启动命令
CMD ["uvicorn", "mortgage_agent.api:app", "--host", "0.0.0.0", "--port", "8000"]

# 暴露端口
EXPOSE 8000

