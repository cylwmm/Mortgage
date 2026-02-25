#!/bin/bash

#######################################################
# 服务器初始化脚本
#
# 在新服务器上运行此脚本来配置部署环境
#
# 使用方式：
#   curl -sSL https://your-repo/scripts/server-init.sh | bash
#
# 或本地运行：
#   bash scripts/server-init.sh
#######################################################

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# 检查是否为 root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "此脚本需要 root 权限，请使用 sudo 运行"
        exit 1
    fi
}

# 更新系统
update_system() {
    log_info "更新系统包..."
    apt-get update
    apt-get upgrade -y
}

# 安装基础工具
install_basics() {
    log_info "安装基础工具..."
    apt-get install -y \
        curl \
        wget \
        git \
        vim \
        htop \
        net-tools \
        ufw \
        fail2ban

    log_success "基础工具安装完成"
}

# 安装 Docker
install_docker() {
    log_info "安装 Docker..."

    if command -v docker &> /dev/null; then
        log_warning "Docker 已安装，跳过"
        return
    fi

    # 移除旧版本
    apt-get remove -y docker docker-engine docker.io containerd runc || true

    # 安装依赖
    apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release

    # 添加 Docker GPG 密钥
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

    # 添加 Docker 仓库
    echo \
        "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
        $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

    # 安装 Docker
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

    log_success "Docker 安装完成"
}

# 安装 Docker Compose
install_docker_compose() {
    log_info "安装 Docker Compose..."

    if command -v docker-compose &> /dev/null; then
        log_warning "Docker Compose 已安装，跳过"
        return
    fi

    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose

    log_success "Docker Compose 安装完成"
}

# 配置防火墙
setup_firewall() {
    log_info "配置防火墙..."

    # 启用 UFW
    ufw --force enable

    # 允许 SSH
    ufw allow 22/tcp

    # 允许 HTTP/HTTPS
    ufw allow 80/tcp
    ufw allow 443/tcp

    # 允许 SSH 但限制连接
    ufw limit 22/tcp

    log_success "防火墙配置完成"
}

# 配置 Fail2Ban
setup_fail2ban() {
    log_info "配置 Fail2Ban（防暴力破解）..."

    systemctl start fail2ban
    systemctl enable fail2ban

    # 创建本地配置
    cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
EOF

    systemctl restart fail2ban

    log_success "Fail2Ban 配置完成"
}

# 创建部署用户
create_deploy_user() {
    local username="deploy"

    log_info "创建部署用户: $username..."

    if id "$username" &>/dev/null; then
        log_warning "用户 $username 已存在，跳过"
        return
    fi

    # 创建用户
    useradd -m -s /bin/bash "$username"

    # 添加到 docker 组（允许运行 docker 命令）
    usermod -aG docker "$username"

    # 创建 SSH 目录
    sudo -u "$username" mkdir -p /home/"$username"/.ssh

    log_success "部署用户创建完成"
    log_info "请配置 SSH 公钥：/home/$username/.ssh/authorized_keys"
}

# 创建应用目录
create_app_directories() {
    log_info "创建应用目录..."

    local app_dir="/home/deploy/mortgage-agent"

    mkdir -p "$app_dir"/{output,logs,backups}
    chown -R deploy:deploy "$app_dir"

    log_success "应用目录创建完成: $app_dir"
}

# 配置 Systemd 服务（可选）
setup_systemd_service() {
    log_info "配置 Systemd 服务..."

    cat > /etc/systemd/system/mortgage-agent.service << 'EOF'
[Unit]
Description=Mortgage Agent Service
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=deploy
WorkingDirectory=/home/deploy/mortgage-agent
ExecStart=/usr/bin/docker-compose up
ExecStop=/usr/bin/docker-compose down
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload

    log_success "Systemd 服务配置完成"
}

# 生成 SSL 自签名证书（开发用）
generate_self_signed_cert() {
    log_info "生成自签名 SSL 证书..."

    local cert_dir="/home/deploy/mortgage-agent/ssl"
    mkdir -p "$cert_dir"

    openssl req -x509 -newkey rsa:4096 -nodes \
        -out "$cert_dir/cert.pem" \
        -keyout "$cert_dir/key.pem" \
        -days 365 \
        -subj "/C=CN/ST=State/L=City/O=Organization/CN=mortgage.local"

    chown -R deploy:deploy "$cert_dir"
    chmod 600 "$cert_dir/key.pem"

    log_success "自签名证书生成完成（开发环境用）"
    log_warning "生产环境请使用 Let's Encrypt 或购买正式证书"
}

# 性能优化
optimize_system() {
    log_info "性能优化..."

    # 增加文件描述符限制
    cat >> /etc/security/limits.conf << 'EOF'
* soft nofile 65535
* hard nofile 65535
* soft nproc 65535
* hard nproc 65535
EOF

    # 调整 Sysctl 参数
    cat >> /etc/sysctl.conf << 'EOF'
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.ip_local_port_range = 10000 65000
EOF

    sysctl -p > /dev/null

    log_success "系统优化完成"
}

# 主函数
main() {
    log_info "=== 开始服务器初始化 ==="

    check_root
    update_system
    install_basics
    install_docker
    install_docker_compose
    setup_firewall
    setup_fail2ban
    create_deploy_user
    create_app_directories
    setup_systemd_service
    generate_self_signed_cert
    optimize_system

    log_success "=== 服务器初始化完成 ==="

    cat << 'EOF'

========================================
后续步骤：
========================================

1. 配置 SSH 密钥（在本地运行）：
   ssh-copy-id -i ~/.ssh/id_rsa.pub deploy@your-server

2. 在 GitHub 仓库设置以下 Secrets（用于 CI/CD）：
   - DOCKER_USERNAME
   - DOCKER_PASSWORD
   - SERVER_USER=deploy
   - SERVER_HOST=your-server-ip
   - SERVER_PORT=22
   - SERVER_PRIVATE_KEY=$(cat ~/.ssh/id_rsa)

3. 登录服务器配置应用：
   ssh deploy@your-server
   cd ~/mortgage-agent
   cp .env.example .env
   # 编辑 .env 文件配置参数

4. 配置 SSL 证书（生产环境）：
   certbot certonly --standalone -d your-domain.com
   cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ssl/cert.pem
   cp /etc/letsencrypt/live/your-domain.com/privkey.pem ssl/key.pem

5. 启动应用：
   docker-compose up -d

6. 验证应用：
   curl http://localhost/health

========================================
EOF
}

# 运行主函数
main "$@"

