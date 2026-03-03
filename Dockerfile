# 阶段 1: 构建 (保持不变)
FROM python:3.11-slim as builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
# 使用 pip install 到当前目录的子文件夹
RUN pip install --no-cache-dir --prefix=/build/install -r requirements.txt

# 阶段 2: 运行
FROM python:3.11-slim
WORKDIR /app

# 关键：将端口改为 8080 避开特权限制
ENV PORT=8080 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.local/bin:$PATH" \
    PYTHONPATH="/app/.local/lib/python3.11/site-packages:$PYTHONPATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    curl \
    # 增加 libcap2-bin 用于给 python 赋权监听 80（如果坚持用80的话）
    libcap2-bin \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser

# 复制依赖
COPY --from=builder /build/install /app/.local
COPY mortgage_agent/ ./mortgage_agent/
COPY README.md .

# 修正权限：确保 appuser 拥有家目录和工作目录
RUN mkdir -p /app/output /app/logs && \
    chown -R appuser:appuser /home/appuser && \
    chown -R appuser:appuser /app

# 如果你一定要监听 80 端口，请解除下面这行的注释（给 python 赋权）
# RUN setcap 'cap_net_bind_service=+ep' /usr/local/bin/python3.11

USER appuser

# 启动命令增加 --log-level debug 以查看更详细报错
CMD ["sh", "-c", "uvicorn mortgage_agent.api:app --host 0.0.0.0 --port ${PORT} --workers 2 --proxy-headers --log-level debug"]