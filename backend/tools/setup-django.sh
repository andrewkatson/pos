#!/bin/bash

###############################################################################
# Django EC2 Setup Script for api.smiling.social
# This script sets up a fresh Ubuntu EC2 instance with Django, Gunicorn, Nginx
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
#     --project-name "your_project" \
#     --domain "smiling.social" \
#     --admin-email "admin@smiling.social"
###############################################################################

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default Configuration Variables
DOMAIN="api.smiling.social"
APP_DIR="/var/www/smiling-social"
GIT_REPO=""
PROJECT_NAME=""
APP_USER="ubuntu"
ADMIN_EMAIL="admin@smiling.social"  # used for Let's Encrypt notifications

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
  --email-user EMAIL            Email address for sending emails
  --email-pass PASSWORD         Email password or app password
  --gemini-api-key KEY          Gemini API key
  --aws-access-key-id KEY       AWS access key ID
  --aws-secret-access-key KEY   AWS secret access key
  --aws-region REGION           AWS region (e.g., us-east-1)
  --aws-storage-bucket NAME     S3 bucket for media storage
  --aws-compressed-bucket NAME  S3 bucket for compressed storage
  --db-name NAME                Database name
  --db-user USER                Database user
  --db-password PASSWORD        Database password
  --db-host HOST                Database host
  --git-repo URL                Git repository URL
  --project-name NAME           Django project name

Optional:
  --db-port PORT                Database port (default: 5432)
  --domain DOMAIN               Domain name (default: api.smiling.social)
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
    --aws-storage-bucket "smiling-media" \\
    --aws-compressed-bucket "smiling-compressed" \\
    --db-name "smilingdb" \\
    --db-user "smilingapp" \\
    --db-password "db-pass" \\
    --db-host "cluster.xxxxx.rds.amazonaws.com" \\
    --git-repo "https://github.com/user/repo.git" \\
    --project-name "your_project"
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
}

setup_firewall() {
    print_status "Configuring firewall..."
    sudo ufw --force enable
    sudo ufw allow OpenSSH
    sudo ufw allow 'Nginx Full'
    sudo ufw status
}

clone_repository() {
    print_status "Cloning application repository..."
    
    if [ -d "$APP_DIR" ]; then
        print_warning "Directory $APP_DIR already exists. Backing up..."
        sudo mv "$APP_DIR" "${APP_DIR}.backup.$(date +%Y%m%d_%H%M%S)"
    fi
    
    sudo mkdir -p "$APP_DIR"
    sudo chown $APP_USER:$APP_USER "$APP_DIR"
    
    git clone "$GIT_REPO" "$APP_DIR"
    cd "$APP_DIR"
}

setup_python_environment() {
    print_status "Setting up Python virtual environment..."
    cd "$APP_DIR"
    
    python3 -m venv venv
    source venv/bin/activate
    
    pip install --upgrade pip
    pip install wheel
    
    if [ -f requirements.txt ]; then
        pip install -r requirements.txt
    else
        print_error "requirements.txt not found!"
        exit 1
    fi
    
    # Install additional required packages
    pip install gunicorn psycopg2-binary dj-database-url python-dotenv
    
    deactivate
}

create_env_file() {
    print_status "Creating .env file..."
    
    cat > "$APP_DIR/.env" << EOF
# Django Settings
DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY
DJANGO_DEBUG=$DJANGO_DEBUG

# Email Configuration
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
    
    chmod 600 "$APP_DIR/.env"
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
    cd "$APP_DIR"
    source venv/bin/activate
    export $(cat .env | xargs)
    
    # Create necessary directories
    mkdir -p staticfiles media
    
    # Run migrations
    python manage.py migrate --noinput || print_warning "Migration failed - check database connection"
    
    # Collect static files
    python manage.py collectstatic --noinput
    
    deactivate
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
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/gunicorn \\
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

setup_nginx() {
    print_status "Configuring Nginx..."
    
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
    
    # Enable site
    sudo ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/
    
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
    print_status "Setting up SSL certificate with Let's Encrypt..."
    print_warning "Make sure DNS is pointing to this server before continuing!"
    
    read -p "Is DNS configured and pointing to this server? (yes/no): " dns_ready
    
    if [ "$dns_ready" = "yes" ]; then
        if sudo certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m $ADMIN_EMAIL; then
            print_status "SSL certificate installed successfully"
        else
            print_error "SSL certificate installation failed. You can run it manually later with:"
            echo "sudo certbot --nginx -d $DOMAIN"
        fi
    else
        print_warning "Skipping SSL setup. Run this command when DNS is ready:"
        echo "sudo certbot --nginx -d $DOMAIN"
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
    
    cat > ~/status_check.sh << 'EOF'
#!/bin/bash

echo "=== Checking Gunicorn ==="
sudo systemctl status gunicorn --no-pager | head -n 3

echo -e "\n=== Checking Nginx ==="
sudo systemctl status nginx --no-pager | head -n 3

echo -e "\n=== Checking Socket ==="
ls -l /var/www/smiling-social/gunicorn.sock 2>/dev/null || echo "Socket not found"

echo -e "\n=== Checking Nginx Ports ==="
sudo netstat -tlnp | grep nginx

echo -e "\n=== Recent Gunicorn Logs ==="
sudo journalctl -u gunicorn -n 5 --no-pager

echo -e "\n=== Testing Local Connection ==="
curl -I http://localhost 2>/dev/null | head -n 1 || echo "Connection failed"
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

cd $APP_DIR

# Pull latest code
git pull origin main

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
pip install -r requirements.txt

# Load environment variables
export \$(cat .env | xargs)

# Run migrations
python manage.py migrate --noinput

# Collect static files
python manage.py collectstatic --noinput

# Restart services
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
    echo "Your Django application has been deployed to: $DOMAIN"
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
    echo "  1. Create Django superuser: cd $APP_DIR && source venv/bin/activate && python manage.py createsuperuser"
    echo "  2. Test your site: http://$DOMAIN (or https if SSL was configured)"
    echo "  3. Check logs if anything isn't working"
    echo ""
    echo "========================================================================="
}

###############################################################################
# Main Execution
###############################################################################

main() {
    clear
    echo "========================================================================="
    echo "Django EC2 Setup Script for api.smiling.social"
    echo "========================================================================="
    echo ""
    
    # Parse command line arguments
    parse_arguments "$@"
    
    check_root
    
    echo ""
    print_status "Starting setup process..."
    print_status "Domain: $DOMAIN"
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
    setup_gunicorn_service
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