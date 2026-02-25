#!/bin/bash

#######################################################
# 部署脚本 - 部署到生产服务器
#
# 使用方式：
#   bash scripts/deploy.sh [production|staging|develop]
#
# 依赖：
#   - SSH 访问权限
#   - Docker & Docker Compose
#   - Git
#######################################################

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT=${1:-production}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${PROJECT_ROOT}/backups"

# 从环境变量或 .env 文件读取配置
load_config() {
    local env_file="${PROJECT_ROOT}/.env"
    if [ -f "$env_file" ]; then
        export $(grep -v '^#' "$env_file" | xargs)
    fi
}

# 日志函数
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

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."

    local deps=("docker" "docker-compose" "git" "ssh")
    for cmd in "${deps[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            log_error "$cmd 未安装"
            exit 1
        fi
    done

    log_success "所有依赖都已安装"
}

# 验证配置
validate_config() {
    log_info "验证配置..."

    if [ -z "$SERVER_USER" ] || [ -z "$SERVER_HOST" ]; then
        log_error "未设置 SERVER_USER 或 SERVER_HOST"
        exit 1
    fi

    log_success "配置验证通过"
}

# 构建 Docker 镜像
build_image() {
    log_info "构建 Docker 镜像..."

    local image_tag="${DOCKER_USERNAME}/mortgage-agent:${ENVIRONMENT}-${TIMESTAMP}"

    docker build \
        --tag "$image_tag" \
        --tag "${DOCKER_USERNAME}/mortgage-agent:${ENVIRONMENT}-latest" \
        --build-arg BUILD_DATE="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
        --build-arg VCS_REF="$(git rev-parse --short HEAD)" \
        "$PROJECT_ROOT"

    log_success "镜像构建完成: $image_tag"
    echo "$image_tag"
}

# 推送镜像到仓库
push_image() {
    local image_tag=$1

    log_info "推送镜像到 Docker Hub..."

    docker push "$image_tag"
    docker push "${DOCKER_USERNAME}/mortgage-agent:${ENVIRONMENT}-latest"

    log_success "镜像推送完成"
}

# 连接到服务器并部署
deploy_to_server() {
    local image_tag=$1
    local deploy_path="/home/${SERVER_USER}/mortgage-agent"

    log_info "连接到服务器: ${SERVER_USER}@${SERVER_HOST}"

    # SSH 连接并执行远程命令
    ssh -v "${SERVER_USER}@${SERVER_HOST}" << SSHEOF
set -e

log_info() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] \$1"
}

log_success() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [SUCCESS] \$1"
}

log_error() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] \$1"
}

cd "$deploy_path" || { log_error "部署目录不存在"; exit 1; }

log_info "=== 开始部署 ==="

# 备份当前配置
log_info "备份当前配置..."
mkdir -p backups
if [ -f "docker-compose.yml" ]; then
    cp docker-compose.yml "backups/docker-compose.yml.${TIMESTAMP}"
fi
if [ -f ".env" ]; then
    cp .env "backups/.env.${TIMESTAMP}"
fi

# 拉取最新代码
log_info "拉取最新代码..."
git fetch origin
git checkout ${ENVIRONMENT}
git pull origin ${ENVIRONMENT}

# 停止旧容器
log_info "停止旧容器..."
docker-compose down || true

# 设置新镜像标签
log_info "更新镜像标签..."
export DOCKER_IMAGE="${image_tag}"

# 启动新容器
log_info "启动新容器..."
docker-compose up -d

# 等待服务启动
log_info "等待服务启动..."
sleep 10

# 检查健康状态
log_info "检查服务健康状态..."
max_attempts=30
attempt=0
while [ \$attempt -lt \$max_attempts ]; do
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        log_success "服务已启动且健康"
        break
    fi
    echo "等待服务启动... (\$((attempt + 1))/\$max_attempts)"
    sleep 2
    ((attempt++))
done

if [ \$attempt -eq \$max_attempts ]; then
    log_error "服务启动失败"
    exit 1
fi

# 查看容器日志
log_info "最近的容器日志："
docker-compose logs --tail=20

log_success "=== 部署完成 ==="

SSHEOF

    local ssh_exit_code=$?
    if [ $ssh_exit_code -ne 0 ]; then
        log_error "远程部署失败 (退出码: $ssh_exit_code)"
        exit 1
    fi

    log_success "服务器部署完成"
}

# 验证部署
verify_deployment() {
    log_info "验证部署..."

    local max_attempts=30
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if curl -f "http://${SERVER_HOST}/health" > /dev/null 2>&1; then
            log_success "部署验证通过"
            return 0
        fi
        echo "等待服务启动... ($((attempt + 1))/$max_attempts)"
        sleep 10
        ((attempt++))
    done

    log_error "部署验证失败"
    exit 1
}

# 回滚部署
rollback() {
    log_warning "执行回滚..."

    ssh "${SERVER_USER}@${SERVER_HOST}" << SSHEOF
set -e
cd /home/${SERVER_USER}/mortgage-agent

# 获取最近的备份
latest_backup=\$(ls -t backups/docker-compose.yml.* 2>/dev/null | head -1)

if [ -z "\$latest_backup" ]; then
    echo "没有可用的备份"
    exit 1
fi

cp "\$latest_backup" docker-compose.yml
docker-compose down || true
docker-compose up -d

echo "回滚完成"
SSHEOF

    log_success "回滚完成"
}

# 主函数
main() {
    log_info "=== 开始部署流程 ==="
    log_info "环境: $ENVIRONMENT"
    log_info "时间戳: $TIMESTAMP"

    load_config
    check_dependencies
    validate_config

    # 构建镜像
    local image_tag=$(build_image)

    # 推送镜像
    push_image "$image_tag"

    # 部署到服务器
    deploy_to_server "$image_tag"

    # 验证部署
    verify_deployment

    log_success "=== 部署流程完成 ==="
    log_success "应用地址: https://${SERVER_HOST}"
    log_success "Swagger 文档: https://${SERVER_HOST}/docs"
}

# 错误处理
trap 'log_error "部署失败"; exit 1' ERR

# 运行主函数
main "$@"

