#!/bin/bash

#######################################################
# 一键配置 GitHub Secrets
#
# 使用方式：
#   bash scripts/setup-github-secrets.sh \
#     --username your_docker_username \
#     --password your_docker_password \
#     --server-host 123.45.67.89 \
#     --server-user deploy
#
# 或使用环境变量：
#   export DOCKER_USERNAME=xxx
#   export DOCKER_PASSWORD=xxx
#   export SERVER_HOST=xxx
#   export SERVER_USER=deploy
#   bash scripts/setup-github-secrets.sh
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

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."

    if ! command -v gh &> /dev/null; then
        log_error "GitHub CLI 未安装"
        echo "请先安装 GitHub CLI: https://cli.github.com/"
        exit 1
    fi

    # 检查是否已登录
    if ! gh auth status > /dev/null 2>&1; then
        log_error "未登录 GitHub"
        echo "请运行: gh auth login"
        exit 1
    fi

    log_success "依赖检查通过"
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --username)
                DOCKER_USERNAME="$2"
                shift 2
                ;;
            --password)
                DOCKER_PASSWORD="$2"
                shift 2
                ;;
            --server-host)
                SERVER_HOST="$2"
                shift 2
                ;;
            --server-user)
                SERVER_USER="$2"
                shift 2
                ;;
            *)
                log_error "未知选项: $1"
                exit 1
                ;;
        esac
    done
}

# 交互式输入（如果未通过参数提供）
interactive_input() {
    if [ -z "$DOCKER_USERNAME" ]; then
        read -p "Docker Hub 用户名: " DOCKER_USERNAME
    fi

    if [ -z "$DOCKER_PASSWORD" ]; then
        read -sp "Docker Hub 密码或 Token: " DOCKER_PASSWORD
        echo
    fi

    if [ -z "$SERVER_HOST" ]; then
        read -p "服务器 IP 或域名: " SERVER_HOST
    fi

    if [ -z "$SERVER_USER" ]; then
        read -p "服务器用户名 [deploy]: " SERVER_USER
        SERVER_USER="${SERVER_USER:-deploy}"
    fi

    if [ -z "$SERVER_PORT" ]; then
        read -p "SSH 端口 [22]: " SERVER_PORT
        SERVER_PORT="${SERVER_PORT:-22}"
    fi
}

# 获取 SSH 私钥
get_ssh_private_key() {
    local key_path="${1:-$HOME/.ssh/id_rsa}"

    if [ ! -f "$key_path" ]; then
        log_error "SSH 私钥不存在: $key_path"
        echo ""
        echo "请运行以下命令生成 SSH 密钥对："
        echo "  ssh-keygen -t rsa -f ~/.ssh/id_rsa -N \"\""
        echo ""
        echo "然后运行以下命令添加公钥到服务器："
        echo "  ssh-copy-id -i ~/.ssh/id_rsa.pub $SERVER_USER@$SERVER_HOST"
        exit 1
    fi

    cat "$key_path"
}

# 设置 Secrets
set_secrets() {
    log_info "设置 GitHub Secrets..."

    # 获取当前仓库
    local repo=$(gh repo view --json nameWithOwner -q)

    log_info "目标仓库: $repo"
    echo ""

    # 设置 Docker Secrets
    log_info "设置 DOCKER_USERNAME"
    gh secret set DOCKER_USERNAME --body "$DOCKER_USERNAME" -R "$repo"
    log_success "✓ DOCKER_USERNAME 已设置"

    log_info "设置 DOCKER_PASSWORD"
    gh secret set DOCKER_PASSWORD --body "$DOCKER_PASSWORD" -R "$repo"
    log_success "✓ DOCKER_PASSWORD 已设置"

    # 设置服务器 Secrets
    log_info "设置 SERVER_USER"
    gh secret set SERVER_USER --body "$SERVER_USER" -R "$repo"
    log_success "✓ SERVER_USER 已设置"

    log_info "设置 SERVER_HOST"
    gh secret set SERVER_HOST --body "$SERVER_HOST" -R "$repo"
    log_success "✓ SERVER_HOST 已设置"

    log_info "设置 SERVER_PORT"
    gh secret set SERVER_PORT --body "$SERVER_PORT" -R "$repo"
    log_success "✓ SERVER_PORT 已设置"

    # 设置 SSH 私钥
    log_info "设置 SERVER_PRIVATE_KEY"
    local private_key=$(get_ssh_private_key)
    gh secret set SERVER_PRIVATE_KEY --body "$private_key" -R "$repo"
    log_success "✓ SERVER_PRIVATE_KEY 已设置"

    echo ""
    log_success "所有 Secrets 设置完成！"
}

# 验证配置
verify_config() {
    log_info "验证配置..."

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📝 配置信息"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Docker Username:  $DOCKER_USERNAME"
    echo "Docker Password:  [已掩码]"
    echo "Server Host:      $SERVER_HOST"
    echo "Server User:      $SERVER_USER"
    echo "Server Port:      $SERVER_PORT"
    echo "SSH Key:          $([ -f ~/.ssh/id_rsa ] && echo '✓ 已配置' || echo '✗ 未配置')"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # 测试 SSH 连接
    log_info "测试 SSH 连接..."
    if ssh -i ~/.ssh/id_rsa \
        -p "$SERVER_PORT" \
        -o StrictHostKeyChecking=accept-new \
        -o ConnectTimeout=5 \
        "$SERVER_USER@$SERVER_HOST" \
        "docker --version" > /dev/null 2>&1; then
        log_success "✓ SSH 连接正常"
    else
        log_warning "✗ SSH 连接失败（可能是网络问题）"
        echo ""
        echo "请手动验证 SSH 连接："
        echo "  ssh -i ~/.ssh/id_rsa -p $SERVER_PORT $SERVER_USER@$SERVER_HOST"
    fi

    echo ""
}

# 主函数
main() {
    log_info "=== GitHub Secrets 配置向导 ==="
    echo ""

    # 解析命令行参数
    parse_args "$@"

    # 检查依赖
    check_dependencies

    # 交互式输入
    interactive_input

    echo ""

    # 验证配置
    verify_config

    # 确认操作
    read -p "确定要设置这些 Secrets 吗？(y/n): " confirm
    if [ "$confirm" != "y" ]; then
        log_warning "已取消"
        exit 0
    fi

    echo ""

    # 设置 Secrets
    set_secrets

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ 配置完成！"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "后续步骤："
    echo "  1. 推送代码：git push origin main"
    echo "  2. 查看部署：GitHub Actions 标签页"
    echo ""
}

# 错误处理
trap 'log_error "配置失败"; exit 1' ERR

# 运行主函数
main "$@"

