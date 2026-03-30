#!/bin/bash
# =========================================================
# OutlookRegister + outlookEmailPlus 一键部署脚本
# 适用于 CentOS 10 (Google Cloud VPS)
# 用法: bash deploy.sh
# =========================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
err()   { echo -e "${RED}[✗]${NC} $1"; }
info()  { echo -e "${CYAN}[i]${NC} $1"; }

# =========================================================
# 1. 系统检查
# =========================================================
info "检查系统环境..."

if [ "$(id -u)" -ne 0 ]; then
    err "请使用 root 权限运行此脚本: sudo bash deploy.sh"
    exit 1
fi

# =========================================================
# 2. 安装 Docker (如果未安装)
# =========================================================
if ! command -v docker &> /dev/null; then
    info "正在安装 Docker..."

    # CentOS 10 / RHEL 系使用 dnf
    dnf install -y dnf-plugins-core
    dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
    dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    systemctl enable docker
    systemctl start docker
    log "Docker 安装完成"
else
    log "Docker 已安装: $(docker --version)"
fi

# 确保 Docker Compose 可用
if ! docker compose version &> /dev/null; then
    err "Docker Compose 插件未安装。请运行: dnf install -y docker-compose-plugin"
    exit 1
fi
log "Docker Compose 可用: $(docker compose version --short)"

# =========================================================
# 3. 生成 .env 配置文件
# =========================================================
ENV_FILE=".env"

if [ ! -f "$ENV_FILE" ]; then
    info "生成 .env 配置文件..."

    # 自动生成 SECRET_KEY
    SECRET_KEY=$(openssl rand -hex 32)

    cat > "$ENV_FILE" <<EOF
# =========================================================
#  OutlookRegister 部署配置
#  请根据实际情况修改以下参数
# =========================================================

# --- Manager (outlookEmailPlus) 配置 ---
# 管理器对外暴露的端口
MANAGER_PORT=5000

# Flask 会话加密密钥（已自动生成，请勿泄露）
SECRET_KEY=${SECRET_KEY}

# 管理器登录密码
LOGIN_PASSWORD=admin123

# 是否允许在设置页修改登录密码
ALLOW_LOGIN_PASSWORD_CHANGE=true

# --- Outlook OAuth 配置（可选） ---
# 从 Azure Portal 获取
OAUTH_CLIENT_ID=
OAUTH_REDIRECT_URI=
EOF

    log ".env 文件已生成"
    warn "请编辑 .env 文件填入你的实际配置！"
else
    log ".env 文件已存在，跳过生成"
fi

# =========================================================
# 4. 同步 config.json 中的 manager 密码
# =========================================================
info "同步 config.json 中的 manager 配置..."

# 从 .env 读取 LOGIN_PASSWORD
source "$ENV_FILE"
LOGIN_PWD="${LOGIN_PASSWORD:-admin123}"

# 使用 python3 更新 config.json（避免安装 jq）
if [ -f "config.json" ]; then
    python3 -c "
import json
with open('config.json', 'r', encoding='utf-8') as f:
    cfg = json.load(f)
cfg['manager_url'] = 'http://manager:5000'
cfg['manager_login_password'] = '${LOGIN_PWD}'
with open('config.json', 'w', encoding='utf-8') as f:
    json.dump(cfg, f, indent=4, ensure_ascii=False)
print('config.json 已更新')
"
fi

# =========================================================
# 5. 防火墙配置
# =========================================================
info "配置防火墙..."

if command -v firewall-cmd &> /dev/null; then
    MANAGER_PORT="${MANAGER_PORT:-5000}"
    firewall-cmd --permanent --add-port="${MANAGER_PORT}/tcp" 2>/dev/null || true
    firewall-cmd --reload 2>/dev/null || true
    log "防火墙已开放端口 ${MANAGER_PORT}"
else
    warn "未检测到 firewalld，请手动确保端口已开放"
fi

# =========================================================
# 6. 构建并启动服务
# =========================================================
info "拉取 Manager 镜像..."
docker compose pull manager

info "构建 Registrar 镜像..."
docker compose build registrar

info "启动 Manager 服务..."
docker compose up -d manager

# 等待 Manager 健康
info "等待 Manager 健康检查通过..."
for i in $(seq 1 30); do
    if docker compose exec manager python -c "import urllib.request as u; u.urlopen('http://localhost:5000/healthz', timeout=4).read()" 2>/dev/null; then
        log "Manager 已就绪"
        break
    fi
    if [ "$i" -eq 30 ]; then
        err "Manager 启动超时，请检查日志: docker compose logs manager"
        exit 1
    fi
    sleep 2
done

echo ""
echo "==========================================================="
echo -e " ${GREEN}部署完成！${NC}"
echo "==========================================================="
echo ""
echo -e " ${CYAN}管理器地址:${NC} http://<你的VPS公网IP>:${MANAGER_PORT:-5000}"
echo -e " ${CYAN}登录密码:${NC}   ${LOGIN_PASSWORD:-admin123}"
echo ""
echo -e " ${YELLOW}常用命令:${NC}"
echo "   查看服务状态:    docker compose ps"
echo "   查看管理器日志:  docker compose logs -f manager"
echo "   启动注册任务:    docker compose run --rm registrar"
echo "   停止所有服务:    docker compose down"
echo "   重启管理器:      docker compose restart manager"
echo ""
echo -e " ${YELLOW}注意:${NC}"
echo "   1. 注册机需要代理才能工作，请在 config.json 中配置 proxy"
echo "   2. 每次运行注册任务: docker compose run --rm registrar"
echo "   3. 注册成功的账号会自动推送到管理器"
echo ""
