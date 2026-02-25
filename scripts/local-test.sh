#!/bin/bash

#######################################################
# 本地测试脚本 - 在部署前测试 Docker 镜像
#
# 使用方式：
#   bash scripts/local-test.sh
#
# 依赖：
#   - Docker
#   - Docker Compose
#######################################################

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# 检查 Docker
check_docker() {
    log_info "检查 Docker 环境..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose 未安装"
        exit 1
    fi

    log_success "Docker 环境检查通过"
}

# 构建本地镜像
build_local_image() {
    log_info "构建本地 Docker 镜像..."

    docker build -t mortgage-agent:latest .

    log_success "镜像构建完成"
}

# 启动测试容器
start_containers() {
    log_info "启动容器..."

    # 设置测试环境变量
    export DOCKER_IMAGE="mortgage-agent:latest"
    export DOCKER_USERNAME="local"
    export LOG_LEVEL="debug"

    # 修改 docker-compose.yml 以使用本地镜像
    cat > docker-compose.test.yml << 'EOF'
version: '3.9'

services:
  mortgage-api:
    image: mortgage-agent:latest
    container_name: mortgage-api-test
    restart: no
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      PYTHONUNBUFFERED: "1"
      LOG_LEVEL: "debug"
    volumes:
      - ./output:/app/output
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 5s
      timeout: 3s
      retries: 10
      start_period: 5s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  nginx:
    image: nginx:1.25-alpine
    container_name: mortgage-nginx-test
    restart: no
    ports:
      - "127.0.0.1:80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./logs/nginx:/var/log/nginx
    depends_on:
      - mortgage-api
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
EOF

    docker-compose -f docker-compose.test.yml up -d

    log_success "容器启动完成"
}

# 等待服务启动
wait_for_service() {
    log_info "等待服务启动..."

    local max_attempts=60
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if curl -f http://localhost:8000/health > /dev/null 2>&1; then
            log_success "服务已启动"
            return 0
        fi
        echo "等待服务启动... ($((attempt + 1))/$max_attempts)"
        sleep 1
        ((attempt++))
    done

    log_error "服务启动超时"
    docker-compose -f docker-compose.test.yml logs mortgage-api
    exit 1
}

# 运行测试
run_tests() {
    log_info "运行功能测试..."

    # 测试 1: 健康检查
    log_info "测试 1: 健康检查"
    response=$(curl -s http://localhost:8000/health)
    if echo "$response" | grep -q "ok"; then
        log_success "✓ 健康检查通过"
    else
        log_error "✗ 健康检查失败"
        exit 1
    fi

    # 测试 2: Swagger 文档
    log_info "测试 2: Swagger 文档"
    response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs)
    if [ "$response" = "200" ]; then
        log_success "✓ Swagger 文档可访问"
    else
        log_error "✗ Swagger 文档不可访问 (HTTP $response)"
        exit 1
    fi

    # 测试 3: API 请求示例
    log_info "测试 3: API 请求"
    response=$(curl -s -X POST http://localhost:8000/v1/mortgages/prepayment:calc \
      -H "Content-Type: application/json" \
      -d '{
        "principal": 1000000,
        "annual_rate": 3.5,
        "term_months": 360,
        "method": "equal_payment",
        "paid_periods": 24,
        "prepay_amount": 100000,
        "invest_annual_rate": 2.5
      }')

    if echo "$response" | grep -q "savings_shorten_interest"; then
        log_success "✓ API 请求成功"
        echo "  响应: $response"
    else
        log_error "✗ API 请求失败"
        echo "  响应: $response"
        exit 1
    fi

    # 测试 4: Nginx 反向代理
    log_info "测试 4: Nginx 反向代理"
    response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/health)
    if [ "$response" = "200" ]; then
        log_success "✓ Nginx 反向代理正常"
    else
        log_error "✗ Nginx 反向代理异常 (HTTP $response)"
        docker-compose -f docker-compose.test.yml logs nginx
        exit 1
    fi

    log_success "所有测试通过！"
}

# 查看日志
show_logs() {
    log_info "容器日志："
    echo ""
    docker-compose -f docker-compose.test.yml logs --tail=30
}

# 清理
cleanup() {
    log_info "清理测试环境..."

    docker-compose -f docker-compose.test.yml down || true
    rm -f docker-compose.test.yml

    log_success "清理完成"
}

# 主函数
main() {
    log_info "=== 开始本地测试 ==="

    check_docker
    build_local_image
    start_containers
    wait_for_service
    run_tests
    show_logs

    log_success "=== 测试完成 ==="
    log_warning "容器仍在运行，继续使用请访问 http://localhost:8000/docs"
    log_warning "运行 'docker-compose -f docker-compose.test.yml down' 停止容器"
}

# 错误处理
trap 'log_error "测试失败"; cleanup; exit 1' ERR

# 运行主函数
main "$@"

