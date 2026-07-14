#!/bin/bash

###############################################################################
# EC2 Setup Script for smiling.social
#
# Provisions a fresh Ubuntu EC2 instance to serve BOTH:
#   * the Django API  at  api.smiling.social  (gunicorn + nginx, unix socket)
#   * the React/Vite website at smiling.social (static SPA built to website/dist,
#     served by nginx on the same box)
#
# Repo layout on the host (matches production): the repo is cloned into
#   $APP_DIR/pos              -> REPO_DIR
# so Django lives at
#   $APP_DIR/pos/backend      -> BACKEND_DIR   (manage.py, requirements.txt, venv, .env)
# and the website at
#   $APP_DIR/pos/website      -> FRONTEND_DIR  (built into website/dist)
#
# Usage:
#   ./setup-django.sh \
#     --django-secret-key "your-secret-key" \
#     --email-user "your-email@gmail.com" \
#     --email-pass "your-app-password" \
#     --gemini-api-key "your-gemini-key" \
#     --aws-access-key-id "your-aws-access-key" \
#     --aws-secret-access-key "your-aws-secret-key" \
#     --aws-region "us-east-1" \
#     --aws-storage-bucket "bucket-name" \
#     --aws-compressed-bucket "compressed-bucket-name" \
#     --db-name "smilingdb" \
#     --db-user "smilingapp" \
#     --db-password "db-password" \
#     --db-host "cluster.xxxxx.rds.amazonaws.com" \
#     --db-port "5432" \
#     --git-repo "https://github.com/user/repo.git" \
#     --project-name "pos_backend" \
#     --domain "api.smiling.social" \
#     --frontend-domain "smiling.social" \
#     --admin-ip-allowlist "1.2.3.4" \
#     --admin-email "admin@smiling.social"
###############################################################################

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default Configuration Variables
DOMAIN="api.smiling.social"           # backend/API host
FRONTEND_DOMAIN="smiling.social"      # website host (apex; www is added too)
APP_DIR="/var/www/smiling-social"
REPO_DIR="$APP_DIR/pos"               # repo is cloned here (nested, matches prod)
BACKEND_DIR="$REPO_DIR/backend"       # Django project root (manage.py lives here)
FRONTEND_DIR="$REPO_DIR/website"      # Vite SPA root
GIT_REPO=""
PROJECT_NAME=""                       # Django project package, e.g. pos_backend
APP_USER="ubuntu"
ADMIN_EMAIL="admin@smiling.social"    # used for Let's Encrypt notifications

# Environment Variables (from command line)
DJANGO_SECRET_KEY=""
EMAIL_USER=""
EMAIL_PASS=""
GEMINI_API_KEY=""
AWS_ACCESS_KEY_ID=""
AWS_SECRET_ACCESS_KEY=""
AWS_REGION=""
AWS_STORAGE_BUCKET_NAME=""
AWS_COMPRESSED_STORAGE_BUCKET_NAME=""
DATABASE_NAME=""
DATABASE_USER=""
DATABASE_PASSWORD=""
DATABASE_HOST=""
DATABASE_PORT="5432"
ADMIN_IP_ALLOWLIST=""                 # optional: exact public IP(s) allowed to reach /admin

# Django Settings
DJANGO_DEBUG="False"

###############################################################################
# Helper Functions
###############################################################################

print_status() {
    echo -e "${GREEN}==>${NC} $1"
}

print_error() {
    echo -e "${RED}ERROR:${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}WARNING:${NC} $1"
}

check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_error "This script should NOT be run as root. Run as ubuntu user."
        exit 1
    fi
}

print_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Required Options:
  --django-secret-key KEY       Django secret key
  --email-user EMAIL            Gmail address used to send verification emails
  --email-pass PASSWORD         Gmail app password
  --gemini-api-key KEY          Gemini API key
  --aws-access-key-id KEY       AWS access key ID
  --aws-secret-access-key KEY   AWS secret access key
  --aws-region REGION           AWS region (e.g., us-east-1)
  --aws-storage-bucket NAME     S3 bucket for original images
  --aws-compressed-bucket NAME  S3 bucket for compressed images
  --db-name NAME                Database name
  --db-user USER                Database user
  --db-password PASSWORD        Database password
  --db-host HOST                Database host
  --git-repo URL                Git repository URL
  --project-name NAME           Django project package name (e.g. pos_backend)

Optional:
  --db-port PORT                Database port (default: 5432)
  --domain DOMAIN               API/backend host (default: api.smiling.social)
  --frontend-domain DOMAIN      Website host (default: smiling.social)
  --admin-ip-allowlist IPS      Comma-separated exact IPs allowed to reach /admin
  --admin-email EMAIL           Admin email for Let's Encrypt
  --help                        Show this help message

Example:
  $0 \\
    --django-secret-key "your-secret-key" \\
    --email-user "app@gmail.com" \\
    --email-pass "app-password" \\
    --gemini-api-key "your-key" \\
    --aws-access-key-id "AKIA..." \\
    --aws-secret-access-key "secret..." \\
    --aws-region "us-east-1" \\
    --aws-storage-bucket "goodvibesonly-images" \\
    --aws-compressed-bucket "goodvibesonly-imagescompressed" \\
    --db-name "smilingdb" \\
    --db-user "smilingapp" \\
    --db-password "db-pass" \\
    --db-host "cluster.xxxxx.rds.amazonaws.com" \\
    --git-repo "https://github.com/user/repo.git" \\
    --project-name "pos_backend"
EOF
    exit 0
}

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --django-secret-key)
                DJANGO_SECRET_KEY="$2"
                shift 2
                ;;
            --email-user)
                EMAIL_USER="$2"
                shift 2
                ;;
            --email-pass)
                EMAIL_PASS="$2"
                shift 2
                ;;
            --gemini-api-key)
                GEMINI_API_KEY="$2"
                shift 2
                ;;
            --aws-access-key-id)
                AWS_ACCESS_KEY_ID="$2"
                shift 2
                ;;
            --aws-secret-access-key)
                AWS_SECRET_ACCESS_KEY="$2"
                shift 2
                ;;
            --aws-region)
                AWS_REGION="$2"
                shift 2
                ;;
            --aws-storage-bucket)
                AWS_STORAGE_BUCKET_NAME="$2"
                shift 2
                ;;
            --aws-compressed-bucket)
                AWS_COMPRESSED_STORAGE_BUCKET_NAME="$2"
                shift 2
                ;;
            --db-name)
                DATABASE_NAME="$2"
                shift 2
                ;;
            --db-user)
                DATABASE_USER="$2"
                shift 2
                ;;
            --db-password)
                DATABASE_PASSWORD="$2"
                shift 2
                ;;
            --db-host)
                DATABASE_HOST="$2"
                shift 2
                ;;
            --db-port)
                DATABASE_PORT="$2"
                shift 2
                ;;
            --git-repo)
                GIT_REPO="$2"
                shift 2
                ;;
            --project-name)
                PROJECT_NAME="$2"
                shift 2
                ;;
            --domain)
                DOMAIN="$2"
                shift 2
                ;;
            --frontend-domain)
                FRONTEND_DOMAIN="$2"
                shift 2
                ;;
            --admin-ip-allowlist)
                ADMIN_IP_ALLOWLIST="$2"
                shift 2
                ;;
            --admin-email)
                ADMIN_EMAIL="$2"
                shift 2
                ;;
            --help)
                print_usage
                ;;
            *)
                print_error "Unknown option: $1"
                print_usage
                ;;
        esac
    done

    # Validate required parameters
    local missing_params=()

    [[ -z "$DJANGO_SECRET_KEY" ]] && missing_params+=("--django-secret-key")
    [[ -z "$EMAIL_USER" ]] && missing_params+=("--email-user")
    [[ -z "$EMAIL_PASS" ]] && missing_params+=("--email-pass")
    [[ -z "$GEMINI_API_KEY" ]] && missing_params+=("--gemini-api-key")
    [[ -z "$AWS_ACCESS_KEY_ID" ]] && missing_params+=("--aws-access-key-id")
    [[ -z "$AWS_SECRET_ACCESS_KEY" ]] && missing_params+=("--aws-secret-access-key")
    [[ -z "$AWS_REGION" ]] && missing_params+=("--aws-region")
    [[ -z "$AWS_STORAGE_BUCKET_NAME" ]] && missing_params+=("--aws-storage-bucket")
    [[ -z "$AWS_COMPRESSED_STORAGE_BUCKET_NAME" ]] && missing_params+=("--aws-compressed-bucket")
    [[ -z "$DATABASE_NAME" ]] && missing_params+=("--db-name")
    [[ -z "$DATABASE_USER" ]] && missing_params+=("--db-user")
    [[ -z "$DATABASE_PASSWORD" ]] && missing_params+=("--db-password")
    [[ -z "$DATABASE_HOST" ]] && missing_params+=("--db-host")
    [[ -z "$GIT_REPO" ]] && missing_params+=("--git-repo")
    [[ -z "$PROJECT_NAME" ]] && missing_params+=("--project-name")

    if [ ${#missing_params[@]} -gt 0 ]; then
        print_error "Missing required parameters:"
        for param in "${missing_params[@]}"; do
            echo "  $param"
        done
        echo ""
        print_usage
    fi
}

###############################################################################
# Main Setup Functions
###############################################################################

update_system() {
    print_status "Updating system packages..."
    sudo apt update
    sudo apt upgrade -y
}

install_dependencies() {
    print_status "Installing system dependencies..."
    sudo apt install -y \
        python3-pip \
        python3-venv \
        python3-dev \
        nginx \
        postgresql-client \
        git \
        certbot \
        python3-certbot-nginx \
        build-essential \
        libpq-dev \
        curl \
        ufw

    # Node.js (for building the Vite SPA). Vite 8 needs Node 20+, so pull a
    # current LTS from NodeSource rather than Ubuntu's older packaged node.
    if ! command -v node > /dev/null 2>&1; then
        print_status "Installing Node.js 22 (NodeSource)..."
        curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
        sudo apt install -y nodejs
    fi
}

setup_firewall() {
    print_status "Configuring firewall..."
    sudo ufw --force enable
    sudo ufw allow OpenSSH
    sudo ufw allow 'Nginx Full'
    sudo ufw status
}

clone_repository() {
    print_status "Cloning application repository into $REPO_DIR..."

    if [ -d "$APP_DIR" ]; then
        print_warning "Directory $APP_DIR already exists. Backing up..."
        sudo mv "$APP_DIR" "${APP_DIR}.backup.$(date +%Y%m%d_%H%M%S)"
    fi

    sudo mkdir -p "$APP_DIR"
    sudo chown $APP_USER:$APP_USER "$APP_DIR"

    # Clone into the nested pos/ directory so paths match production:
    #   $APP_DIR/pos/backend, $APP_DIR/pos/website
    git clone "$GIT_REPO" "$REPO_DIR"
}

setup_python_environment() {
    print_status "Setting up Python virtual environment..."
    cd "$BACKEND_DIR"

    python3 -m venv venv
    source venv/bin/activate

    pip install --upgrade pip
    pip install wheel

    if [ -f requirements.txt ]; then
        pip install -r requirements.txt
    else
        print_error "requirements.txt not found in $BACKEND_DIR!"
        exit 1
    fi

    deactivate
}

create_env_file() {
    print_status "Creating .env file at $BACKEND_DIR/.env ..."

    # Derived defaults for the internet-facing config. ALLOWED_HOSTS gates which
    # Host headers Django accepts (missing => 400 DisallowedHost). CSRF/CORS lists
    # let the website origin log in and call the API cross-origin. FRONTEND_BASE_URL
    # is where the email-verification link points.
    local allowed_hosts="$DOMAIN,localhost,127.0.0.1"
    local csrf_origins="https://$DOMAIN,https://$FRONTEND_DOMAIN,https://www.$FRONTEND_DOMAIN"
    local cors_origins="https://$FRONTEND_DOMAIN,https://www.$FRONTEND_DOMAIN"
    local frontend_base_url="https://$FRONTEND_DOMAIN"

    cat > "$BACKEND_DIR/.env" << EOF
# Django Settings
DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY
DJANGO_DEBUG=$DJANGO_DEBUG

# Public site config
ALLOWED_HOSTS=$allowed_hosts
CSRF_TRUSTED_ORIGINS=$csrf_origins
CORS_ALLOWED_ORIGINS=$cors_origins
FRONTEND_BASE_URL=$frontend_base_url
SECURE_SSL_REDIRECT=True
ADMIN_IP_ALLOWLIST=$ADMIN_IP_ALLOWLIST

# Email Configuration (Gmail SMTP; app password)
EMAIL_USER=$EMAIL_USER
EMAIL_PASS=$EMAIL_PASS

# Gemini API
GEMINI_API_KEY=$GEMINI_API_KEY

# AWS Configuration
AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY
AWS_REGION=$AWS_REGION
AWS_STORAGE_BUCKET_NAME=$AWS_STORAGE_BUCKET_NAME
AWS_COMPRESSED_STORAGE_BUCKET_NAME=$AWS_COMPRESSED_STORAGE_BUCKET_NAME

# Database Configuration
DATABASE_NAME=$DATABASE_NAME
DATABASE_USER=$DATABASE_USER
DATABASE_PASSWORD=$DATABASE_PASSWORD
DATABASE_HOST=$DATABASE_HOST
DATABASE_PORT=$DATABASE_PORT
EOF

    chmod 600 "$BACKEND_DIR/.env"
    print_status ".env file created successfully"
}

test_database_connection() {
    print_status "Testing database connection..."

    if PGPASSWORD=$DATABASE_PASSWORD psql -h $DATABASE_HOST -U $DATABASE_USER -d $DATABASE_NAME -c "SELECT 1;" > /dev/null 2>&1; then
        print_status "Database connection successful!"
    else
        print_error "Cannot connect to database. Please check credentials and security group."
        print_warning "Continuing anyway... fix database connection later."
    fi
}

run_django_setup() {
    print_status "Running Django migrations and collecting static files..."
    cd "$BACKEND_DIR"
    source venv/bin/activate

    # Load .env safely: `set -a` exports everything sourced, and `source` ignores
    # comment/blank lines (unlike `export $(cat .env | xargs)`, which chokes on
    # the "# ..." comment lines above).
    set -a
    source "$BACKEND_DIR/.env"
    set +a

    # Create static/media dirs at the ABSOLUTE paths settings.py pins them to
    # (STATIC_ROOT=$APP_DIR/staticfiles, MEDIA_ROOT=$APP_DIR/media) — collectstatic
    # writes to STATIC_ROOT, and nginx serves from these same paths below.
    mkdir -p "$APP_DIR/staticfiles" "$APP_DIR/media"

    # Run migrations
    python manage.py migrate --noinput || print_warning "Migration failed - check database connection"

    # Collect static files
    python manage.py collectstatic --noinput

    deactivate
}

build_frontend() {
    print_status "Building the website (Vite SPA)..."
    cd "$FRONTEND_DIR"

    # Reproducible install from package-lock.json, then a production build. The
    # API base URL is baked in at build time; point it at the backend host.
    npm ci
    VITE_API_BASE_URL="https://$DOMAIN/user_index" npm run build

    if [ -d "$FRONTEND_DIR/dist" ]; then
        print_status "Website built to $FRONTEND_DIR/dist"
    else
        print_error "Website build did not produce a dist/ directory."
        exit 1
    fi
}

setup_gunicorn_service() {
    print_status "Setting up Gunicorn systemd service..."

    sudo tee /etc/systemd/system/gunicorn.service > /dev/null << EOF
[Unit]
Description=gunicorn daemon for $DOMAIN
After=network.target

[Service]
User=$APP_USER
Group=www-data
WorkingDirectory=$BACKEND_DIR
Environment="PATH=$BACKEND_DIR/venv/bin"
EnvironmentFile=$BACKEND_DIR/.env
ExecStart=$BACKEND_DIR/venv/bin/gunicorn \\
          --access-logfile - \\
          --workers 3 \\
          --bind unix:$APP_DIR/gunicorn.sock \\
          $PROJECT_NAME.wsgi:application

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl start gunicorn
    sudo systemctl enable gunicorn

    # Check status
    if sudo systemctl is-active --quiet gunicorn; then
        print_status "Gunicorn service started successfully"
    else
        print_error "Gunicorn failed to start. Check logs with: sudo journalctl -u gunicorn -n 50"
    fi
}

setup_cleanup_timer() {
    # Schedules the orphan-image S3 cleanup as a daily systemd timer. The job
    # needs both the database (to know which images live Posts still use) and
    # the AWS credentials, so it runs on the app host with the same env as
    # gunicorn rather than from CI, which cannot reach the private database.
    print_status "Setting up orphan-image cleanup systemd timer..."

    sudo tee /etc/systemd/system/cleanup-orphan-images.service > /dev/null << EOF
[Unit]
Description=Delete orphaned post images from S3 for $DOMAIN
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=$APP_USER
Group=www-data
WorkingDirectory=$BACKEND_DIR
Environment="PATH=$BACKEND_DIR/venv/bin"
EnvironmentFile=$BACKEND_DIR/.env
ExecStart=$BACKEND_DIR/venv/bin/python manage.py cleanup_orphan_images
EOF

    sudo tee /etc/systemd/system/cleanup-orphan-images.timer > /dev/null << EOF
[Unit]
Description=Run orphan-image cleanup daily

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable --now cleanup-orphan-images.timer

    if sudo systemctl is-enabled --quiet cleanup-orphan-images.timer; then
        print_status "Orphan-image cleanup timer enabled (daily)"
    else
        print_error "Cleanup timer failed to enable. Check: sudo journalctl -u cleanup-orphan-images -n 50"
    fi
}

setup_nginx() {
    print_status "Configuring Nginx for the API ($DOMAIN)..."

    sudo tee /etc/nginx/sites-available/$DOMAIN > /dev/null << EOF
server {
    listen 80;
    server_name $DOMAIN;

    client_max_body_size 10M;

    location = /favicon.ico {
        access_log off;
        log_not_found off;
    }

    location /static/ {
        alias $APP_DIR/staticfiles/;
    }

    location /media/ {
        alias $APP_DIR/media/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:$APP_DIR/gunicorn.sock;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Host \$host;
    }
}
EOF

    print_status "Configuring Nginx for the website ($FRONTEND_DOMAIN)..."

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

    # Enable both sites
    sudo ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/
    sudo ln -sf /etc/nginx/sites-available/$FRONTEND_DOMAIN /etc/nginx/sites-enabled/

    # Remove default site
    sudo rm -f /etc/nginx/sites-enabled/default

    # Test configuration
    sudo nginx -t

    # Restart Nginx
    sudo systemctl restart nginx
    sudo systemctl enable nginx

    print_status "Nginx configured successfully"
}

setup_ssl() {
    print_status "Setting up SSL certificates with Let's Encrypt..."
    print_warning "Make sure DNS for BOTH $DOMAIN and $FRONTEND_DOMAIN points to this server before continuing!"

    read -p "Is DNS configured and pointing to this server? (yes/no): " dns_ready

    if [ "$dns_ready" = "yes" ]; then
        if sudo certbot --nginx \
            -d $DOMAIN \
            -d $FRONTEND_DOMAIN -d www.$FRONTEND_DOMAIN \
            --non-interactive --agree-tos --redirect -m $ADMIN_EMAIL; then
            print_status "SSL certificates installed successfully"
        else
            print_error "SSL certificate installation failed. You can run it manually later with:"
            echo "sudo certbot --nginx -d $DOMAIN -d $FRONTEND_DOMAIN -d www.$FRONTEND_DOMAIN"
        fi
    else
        print_warning "Skipping SSL setup. Run this command when DNS is ready:"
        echo "sudo certbot --nginx -d $DOMAIN -d $FRONTEND_DOMAIN -d www.$FRONTEND_DOMAIN"
    fi
}

setup_log_rotation() {
    print_status "Setting up log rotation..."

    sudo tee /etc/logrotate.d/gunicorn > /dev/null << EOF
$APP_DIR/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 $APP_USER www-data
    sharedscripts
    postrotate
        systemctl reload gunicorn > /dev/null 2>&1 || true
    endscript
}
EOF

    print_status "Log rotation configured"
}

create_health_check_script() {
    print_status "Creating health check script..."

    cat > ~/status_check.sh << EOF
#!/bin/bash

echo "=== Checking Gunicorn ==="
sudo systemctl status gunicorn --no-pager | head -n 3

echo -e "\n=== Checking Nginx ==="
sudo systemctl status nginx --no-pager | head -n 3

echo -e "\n=== Checking Socket ==="
ls -l $APP_DIR/gunicorn.sock 2>/dev/null || echo "Socket not found"

echo -e "\n=== Checking Nginx Ports ==="
sudo ss -tlnp | grep nginx

echo -e "\n=== Testing API locally ==="
curl -I -H "Host: $DOMAIN" http://localhost 2>/dev/null | head -n 1 || echo "Connection failed"

echo -e "\n=== Testing website locally ==="
curl -I -H "Host: $FRONTEND_DOMAIN" http://localhost 2>/dev/null | head -n 1 || echo "Connection failed"

echo -e "\n=== Recent Gunicorn Logs ==="
sudo journalctl -u gunicorn -n 5 --no-pager
EOF

    chmod +x ~/status_check.sh
    print_status "Health check script created at ~/status_check.sh"
}

set_permissions() {
    print_status "Setting correct permissions..."
    sudo chown -R $APP_USER:www-data "$APP_DIR"
    sudo chmod -R 755 "$APP_DIR"
    sudo chmod 660 "$APP_DIR/gunicorn.sock" 2>/dev/null || true
}

create_update_script() {
    print_status "Creating update/deployment script..."

    cat > ~/update-app.sh << EOF
#!/bin/bash
set -e

echo "Updating application..."

# Pull latest code
cd $REPO_DIR
git pull origin main

# --- Backend ---
cd $BACKEND_DIR
source venv/bin/activate
pip install -r requirements.txt

# Load environment variables (ignores comments/blank lines)
set -a
source $BACKEND_DIR/.env
set +a

python manage.py migrate --noinput
python manage.py collectstatic --noinput
deactivate

# --- Frontend ---
cd $FRONTEND_DIR
npm ci
VITE_API_BASE_URL="https://$DOMAIN/user_index" npm run build

# --- Restart services ---
sudo systemctl restart gunicorn
sudo systemctl reload nginx

echo "Application updated successfully!"
EOF

    chmod +x ~/update-app.sh
    print_status "Update script created at ~/update-app.sh"
}

print_summary() {
    echo ""
    echo "========================================================================="
    echo -e "${GREEN}Setup Complete!${NC}"
    echo "========================================================================="
    echo ""
    echo "API:     https://$DOMAIN"
    echo "Website: https://$FRONTEND_DOMAIN"
    echo ""
    echo "Useful Commands:"
    echo "  - Check server status: ~/status_check.sh"
    echo "  - Update application: ~/update-app.sh"
    echo "  - View Gunicorn logs: sudo journalctl -u gunicorn -f"
    echo "  - View Nginx logs: sudo tail -f /var/log/nginx/error.log"
    echo "  - Restart Gunicorn: sudo systemctl restart gunicorn"
    echo "  - Restart Nginx: sudo systemctl restart nginx"
    echo ""
    echo "Next Steps:"
    echo "  1. Create Django superuser:"
    echo "       cd $BACKEND_DIR && source venv/bin/activate && python manage.py createsuperuser"
    echo "  2. Confirm both hosts resolve to this server and load over HTTPS."
    echo "  3. Register a test user and click the verification link in the email."
    echo ""
    echo "========================================================================="
}

###############################################################################
# Main Execution
###############################################################################

main() {
    clear
    echo "========================================================================="
    echo "EC2 Setup Script for smiling.social (API + website)"
    echo "========================================================================="
    echo ""

    # Parse command line arguments
    parse_arguments "$@"

    check_root

    echo ""
    print_status "Starting setup process..."
    print_status "API domain: $DOMAIN"
    print_status "Website domain: $FRONTEND_DOMAIN"
    print_status "Database: $DATABASE_HOST"
    print_status "Git Repo: $GIT_REPO"
    echo ""

    update_system
    install_dependencies
    setup_firewall
    clone_repository
    setup_python_environment
    create_env_file
    test_database_connection
    run_django_setup
    build_frontend
    setup_gunicorn_service
    setup_cleanup_timer
    setup_nginx
    setup_ssl
    setup_log_rotation
    create_health_check_script
    create_update_script
    set_permissions

    print_summary
}

# Run main function with all arguments
main "$@"
