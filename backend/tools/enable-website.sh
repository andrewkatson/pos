#!/bin/bash

###############################################################################
# enable-website.sh
#
# Brings an ALREADY-provisioned API host (api.smiling.social) up to ALSO serve
# the website (smiling.social) from the same box. This is the delta you run on
# an existing server after pulling the CORS + settings changes — you do NOT need
# to re-run the full setup-django.sh.
#
# It:
#   * installs Node (if missing) and django-cors-headers (via requirements.txt)
#   * ensures the website env vars are present in the backend .env
#   * restarts gunicorn so the new middleware / env take effect
#   * builds the Vite SPA into website/dist
#   * adds an nginx server block for smiling.social with SPA fallback
#   * expands the Let's Encrypt cert to cover the website hosts
#
# Idempotent: safe to re-run. Rather than assume a directory layout, it reads
# the running gunicorn.service for the real Django dir / venv / .env paths, so it
# works whether the repo is nested (pos/backend) or flat (backend).
#
# Run as the ubuntu user (not root). Assumes the updated code is already pulled.
#
# Usage:
#   ./enable-website.sh \
#     [--frontend-domain smiling.social] \
#     [--domain api.smiling.social] \
#     [--app-dir /var/www/smiling-social] \
#     [--admin-email admin@smiling.social] \
#     [--gunicorn-service /etc/systemd/system/gunicorn.service] \
#     [--skip-ssl]
###############################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Defaults
FRONTEND_DOMAIN="smiling.social"
DOMAIN="api.smiling.social"
APP_DIR="/var/www/smiling-social"
ADMIN_EMAIL="admin@smiling.social"
GUNICORN_SERVICE="/etc/systemd/system/gunicorn.service"
RUN_CERTBOT="true"

# Discovered at runtime
BACKEND_DIR=""
FRONTEND_DIR=""
ENV_FILE=""
VENV_BIN=""

print_status()  { echo -e "${GREEN}==>${NC} $1"; }
print_error()   { echo -e "${RED}ERROR:${NC} $1"; }
print_warning() { echo -e "${YELLOW}WARNING:${NC} $1"; }

check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_error "Run this as the ubuntu user, not root."
        exit 1
    fi
}

print_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Optional:
  --frontend-domain DOMAIN   Website host (default: smiling.social)
  --domain DOMAIN            API host, for the combined cert (default: api.smiling.social)
  --app-dir DIR             Deploy root (default: /var/www/smiling-social)
  --admin-email EMAIL       Admin email for Let's Encrypt
  --gunicorn-service PATH   systemd unit to read real paths from
                            (default: /etc/systemd/system/gunicorn.service)
  --skip-ssl                Do not run certbot (configure HTTPS yourself)
  --help                    Show this help
EOF
    exit 0
}

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --frontend-domain)   FRONTEND_DOMAIN="$2"; shift 2 ;;
            --domain)            DOMAIN="$2"; shift 2 ;;
            --app-dir)           APP_DIR="$2"; shift 2 ;;
            --admin-email)       ADMIN_EMAIL="$2"; shift 2 ;;
            --gunicorn-service)  GUNICORN_SERVICE="$2"; shift 2 ;;
            --skip-ssl)          RUN_CERTBOT="false"; shift ;;
            --help)              print_usage ;;
            *) print_error "Unknown option: $1"; print_usage ;;
        esac
    done
}

# Read the real Django dir / venv / .env from the running gunicorn unit, so this
# script mirrors however the host was actually set up rather than guessing.
discover_paths() {
    print_status "Discovering deploy paths..."

    if [ -f "$GUNICORN_SERVICE" ]; then
        BACKEND_DIR=$(awk -F= '/^WorkingDirectory=/{print $2}' "$GUNICORN_SERVICE" | tail -1)
        ENV_FILE=$(awk -F= '/^EnvironmentFile=/{print $2}' "$GUNICORN_SERVICE" | tail -1)
        local exec_bin
        exec_bin=$(awk '/^ExecStart=/{sub(/^ExecStart=/,""); print $1; exit}' "$GUNICORN_SERVICE")
        [ -n "$exec_bin" ] && VENV_BIN=$(dirname "$exec_bin")
    else
        print_warning "$GUNICORN_SERVICE not found; falling back to nested defaults."
    fi

    # Fallbacks (nested layout: $APP_DIR/pos/backend)
    [ -z "$BACKEND_DIR" ] && BACKEND_DIR="$APP_DIR/pos/backend"
    [ -z "$ENV_FILE" ]    && ENV_FILE="$BACKEND_DIR/.env"
    [ -z "$VENV_BIN" ]    && VENV_BIN="$BACKEND_DIR/venv/bin"

    # website/ sits next to backend/ in the repo
    FRONTEND_DIR="$(dirname "$BACKEND_DIR")/website"

    print_status "  Django dir : $BACKEND_DIR"
    print_status "  venv bin   : $VENV_BIN"
    print_status "  env file   : $ENV_FILE"
    print_status "  website dir: $FRONTEND_DIR"

    local ok=true
    [ -f "$BACKEND_DIR/manage.py" ]        || { print_error "manage.py not found in $BACKEND_DIR"; ok=false; }
    [ -f "$ENV_FILE" ]                     || { print_error ".env not found at $ENV_FILE"; ok=false; }
    [ -f "$VENV_BIN/activate" ]            || { print_error "venv not found at $VENV_BIN"; ok=false; }
    [ -f "$FRONTEND_DIR/package.json" ]    || { print_error "website/package.json not found in $FRONTEND_DIR"; ok=false; }
    [ "$ok" = true ] || { print_error "Path discovery failed. Pass --app-dir / --gunicorn-service or fix the paths."; exit 1; }
}

install_node_if_missing() {
    if command -v node > /dev/null 2>&1; then
        print_status "Node already installed ($(node --version))."
        return
    fi
    print_status "Installing Node.js 22 (NodeSource)..."
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
    sudo apt install -y nodejs
}

install_backend_deps() {
    print_status "Installing backend dependencies (picks up django-cors-headers)..."
    # shellcheck disable=SC1090
    source "$VENV_BIN/activate"
    pip install -r "$BACKEND_DIR/requirements.txt"
    deactivate
}

# Append KEY=value to the env file only if KEY is not already present, so re-runs
# never clobber values an operator set by hand.
ensure_env_var() {
    local key="$1" val="$2"
    if grep -q "^${key}=" "$ENV_FILE"; then
        print_status "  $key already set (leaving as-is)"
    else
        echo "${key}=${val}" >> "$ENV_FILE"
        print_status "  added $key"
    fi
}

configure_env() {
    print_status "Ensuring website env vars in $ENV_FILE ..."
    ensure_env_var CORS_ALLOWED_ORIGINS "https://$FRONTEND_DOMAIN,https://www.$FRONTEND_DOMAIN"
    ensure_env_var FRONTEND_BASE_URL "https://$FRONTEND_DOMAIN"

    # CSRF must trust the website origin for cross-origin logins. Don't rewrite an
    # existing value (it may list other origins) — just warn if it omits the site.
    if grep -q "^CSRF_TRUSTED_ORIGINS=" "$ENV_FILE"; then
        if ! grep "^CSRF_TRUSTED_ORIGINS=" "$ENV_FILE" | grep -q "$FRONTEND_DOMAIN"; then
            print_warning "CSRF_TRUSTED_ORIGINS does not include $FRONTEND_DOMAIN."
            print_warning "  Add https://$FRONTEND_DOMAIN (and https://www.$FRONTEND_DOMAIN) or website logins will fail CSRF."
        else
            print_status "  CSRF_TRUSTED_ORIGINS already includes $FRONTEND_DOMAIN"
        fi
    else
        ensure_env_var CSRF_TRUSTED_ORIGINS "https://$DOMAIN,https://$FRONTEND_DOMAIN,https://www.$FRONTEND_DOMAIN"
    fi
}

restart_backend() {
    print_status "Restarting gunicorn to load CORS middleware + new env..."
    sudo systemctl restart gunicorn
    if sudo systemctl is-active --quiet gunicorn; then
        print_status "gunicorn is active."
    else
        print_error "gunicorn failed to start. Check: sudo journalctl -u gunicorn -n 50"
        exit 1
    fi
}

build_frontend() {
    print_status "Building the website (Vite SPA)..."
    cd "$FRONTEND_DIR"
    npm ci
    VITE_API_BASE_URL="https://$DOMAIN/user_index" npm run build
    if [ -d "$FRONTEND_DIR/dist" ]; then
        print_status "Website built to $FRONTEND_DIR/dist"
    else
        print_error "Build did not produce a dist/ directory."
        exit 1
    fi
}

setup_frontend_nginx() {
    print_status "Writing nginx server block for $FRONTEND_DOMAIN ..."

    sudo tee /etc/nginx/sites-available/$FRONTEND_DOMAIN > /dev/null << EOF
server {
    listen 80;
    server_name $FRONTEND_DOMAIN www.$FRONTEND_DOMAIN;

    root $FRONTEND_DIR/dist;
    index index.html;

    # Long-cache the fingerprinted assets Vite emits under /assets/.
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # SPA fallback: unknown paths serve index.html so client-side routing (e.g.
    # /verify-email) works on a hard refresh or a link straight from an email.
    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF

    sudo ln -sf /etc/nginx/sites-available/$FRONTEND_DOMAIN /etc/nginx/sites-enabled/
    sudo nginx -t
    sudo systemctl reload nginx
    print_status "nginx reloaded with the website vhost."
}

setup_ssl() {
    if [ "$RUN_CERTBOT" != "true" ]; then
        print_warning "Skipping certbot (--skip-ssl). Run this when ready:"
        echo "  sudo certbot --nginx -d $DOMAIN -d $FRONTEND_DOMAIN -d www.$FRONTEND_DOMAIN --expand"
        return
    fi
    print_status "Expanding Let's Encrypt cert to cover the website hosts..."
    print_warning "DNS for $FRONTEND_DOMAIN and www.$FRONTEND_DOMAIN must already point to this server."
    if sudo certbot --nginx \
        -d "$DOMAIN" \
        -d "$FRONTEND_DOMAIN" -d "www.$FRONTEND_DOMAIN" \
        --expand --non-interactive --agree-tos --redirect -m "$ADMIN_EMAIL"; then
        print_status "Certificate updated; HTTPS enabled for the website."
    else
        print_error "certbot failed. Once DNS resolves, retry:"
        echo "  sudo certbot --nginx -d $DOMAIN -d $FRONTEND_DOMAIN -d www.$FRONTEND_DOMAIN --expand"
    fi
}

print_summary() {
    echo ""
    echo "========================================================================="
    echo -e "${GREEN}Website enabled${NC}"
    echo "========================================================================="
    echo "API:     https://$DOMAIN"
    echo "Website: https://$FRONTEND_DOMAIN"
    echo ""
    echo "Verify with: ~/status_check.sh   (or backend/tools/status_check.sh)"
    echo "If website logins fail CSRF, add https://$FRONTEND_DOMAIN to CSRF_TRUSTED_ORIGINS"
    echo "in $ENV_FILE and: sudo systemctl restart gunicorn"
    echo "========================================================================="
}

main() {
    parse_arguments "$@"
    check_root
    discover_paths
    install_node_if_missing
    install_backend_deps
    configure_env
    restart_backend
    build_frontend
    setup_frontend_nginx
    setup_ssl
    print_summary
}

main "$@"
