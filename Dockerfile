# 阶段 1: 构建阶段
FROM python:3.11-slim as builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
# 建议使用 --user 安装到特定的文件夹，方便复制
RUN pip install --no-cache-dir --user -r requirements.txt

# 阶段 2: 运行阶段
FROM python:3.11-slim
WORKDIR /app

# 微信云托管建议使用 80 端口
ENV PORT=80 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/home/appuser/.local/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建用户并切换
RUN useradd -m -u 1000 appuser
USER appuser

# 从构建阶段复制依赖（注意路径的变化）
COPY --from=builder /root/.local /home/appuser/.local
COPY mortgage_agent/ ./mortgage_agent/
COPY README.md .

# 微信云托管会自动处理日志，但如果你代码里强行写文件，需要确保权限
RUN mkdir -p /home/appuser/app/output /home/appuser/app/logs

# 健康检查：注意端口改为 80
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://127.0.0.1:80/health || exit 1

# 启动命令：使用环境变量 PORT
CMD ["sh", "-c", "uvicorn mortgage_agent.api:app --host 0.0.0.0 --port ${PORT} --workers 2 --proxy-headers"]