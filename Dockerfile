# 阶段 1: 构建阶段
FROM python:3.11-slim as builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
# 安装到当前目录下的 .local 方便迁移
RUN pip install --no-cache-dir --prefix=/build/install -r requirements.txt

# 阶段 2: 运行阶段
FROM python:3.11-slim
WORKDIR /app

ENV PORT=80 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # 将安装路径加入 PATH 和 PYTHONPATH
    PATH="/app/.local/bin:$PATH" \
    PYTHONPATH="/app/.local/lib/python3.11/site-packages:$PYTHONPATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建用户
RUN useradd -m -u 1000 appuser

# 复制依赖 (从 builder 的安装目录复制到 /app/.local)
COPY --from=builder /build/install /app/.local
# 复制代码
COPY mortgage_agent/ ./mortgage_agent/
COPY README.md .

# 创建输出目录并处理权限
RUN mkdir -p /app/output /app/logs && \
    chown -R appuser:appuser /app

# 切换用户
USER appuser

# 健康检查 (建议先注释掉，等跑通了再开启)
# HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
#    CMD curl -f http://127.0.0.1:80/health || exit 1

CMD ["sh", "-c", "uvicorn mortgage_agent.api:app --host 0.0.0.0 --port ${PORT} --workers 2 --proxy-headers"]