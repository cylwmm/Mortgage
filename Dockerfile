# 阶段 1: 构建阶段 (保持不变)
FROM python:3.11-slim as builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/build/install -r requirements.txt

# 阶段 2: 运行阶段
FROM python:3.11-slim
WORKDIR /app

# 环境变量
ENV PORT=80 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.local/bin:$PATH" \
    PYTHONPATH="/app/.local/lib/python3.11/site-packages:$PYTHONPATH"

# 安装运行时包
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 1. 先创建用户
RUN useradd -m -u 1000 appuser

# 2. 复制所有文件 (此时文件所有者还是 root)
COPY --from=builder /build/install /app/.local
COPY mortgage_agent/ ./mortgage_agent/
COPY README.md .

# 3. 【关键点】在切换用户前，把整个 /app 目录的所有权给 appuser
# 同时创建必要的文件夹
RUN mkdir -p /app/output /app/logs && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app

# 4. 切换到非 root 用户
USER appuser

# 启动命令
CMD ["sh", "-c", "uvicorn mortgage_agent.api:app --host 0.0.0.0 --port ${PORT} --workers 2 --proxy-headers"]