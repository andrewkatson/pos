#!/bin/bash
###############################################################################
# File: credentials.sh
# Store your sensitive credentials here
# Usage: chmod 600 credentials.sh (make readable only by you)
###############################################################################

# Django Configuration
export DJANGO_SECRET_KEY="your-django-secret-key-here"

# Email Configuration
export EMAIL_USER="yourapp@gmail.com"
export EMAIL_PASS="your-email-app-password"

# Gemini API
export GEMINI_API_KEY="your-gemini-api-key"

# AWS Configuration
export AWS_ACCESS_KEY_ID="AKIAXXXXXXXXXXXXXXXX"
export AWS_SECRET_ACCESS_KEY="your-aws-secret-access-key"
export AWS_REGION="us-east-1"
export AWS_STORAGE_BUCKET_NAME="smiling-media-bucket"
export AWS_COMPRESSED_STORAGE_BUCKET_NAME="smiling-compressed-bucket"

# Database Configuration
export DATABASE_NAME="smilingdb"
export DATABASE_USER="smilingapp"
export DATABASE_PASSWORD="your-database-password"
export DATABASE_HOST="smiling-social-cluster.cluster-xxxxx.us-east-1.rds.amazonaws.com"
export DATABASE_PORT="5432"

# Application Configuration
export GIT_REPO="https://github.com/yourusername/your-repo.git"
export PROJECT_NAME="your_project"
export DOMAIN="smiling.social"
export ADMIN_EMAIL="admin@smiling.social"

###############################################################################
# File: run-setup.sh
# Wrapper script to run setup with credentials from credentials.sh
###############################################################################

#!/bin/bash

set -e

# Check if credentials file exists
if [ ! -f ~/credentials.sh ]; then
    echo "ERROR: credentials.sh not found in home directory"
    echo "Please create ~/credentials.sh with your credentials"
    exit 1
fi

# Load credentials
source ~/credentials.sh

# Validate required variables are set
required_vars=(
    "DJANGO_SECRET_KEY"
    "EMAIL_USER"
    "EMAIL_PASS"
    "GEMINI_API_KEY"
    "AWS_ACCESS_KEY_ID"
    "AWS_SECRET_ACCESS_KEY"
    "AWS_REGION"
    "AWS_STORAGE_BUCKET_NAME"
    "AWS_COMPRESSED_STORAGE_BUCKET_NAME"
    "DATABASE_NAME"
    "DATABASE_USER"
    "DATABASE_PASSWORD"
    "DATABASE_HOST"
    "DATABASE_PORT"
    "GIT_REPO"
    "PROJECT_NAME"
    "DOMAIN"
    "ADMIN_EMAIL"
)

missing_vars=()
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo "ERROR: Missing required variables in credentials.sh:"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    exit 1
fi

# Run the setup script
./setup-django.sh \
  --django-secret-key "$DJANGO_SECRET_KEY" \
  --email-user "$EMAIL_USER" \
  --email-pass "$EMAIL_PASS" \
  --gemini-api-key "$GEMINI_API_KEY" \
  --aws-access-key-id "$AWS_ACCESS_KEY_ID" \
  --aws-secret-access-key "$AWS_SECRET_ACCESS_KEY" \
  --aws-region "$AWS_REGION" \
  --aws-storage-bucket "$AWS_STORAGE_BUCKET_NAME" \
  --aws-compressed-bucket "$AWS_COMPRESSED_STORAGE_BUCKET_NAME" \
  --db-name "$DATABASE_NAME" \
  --db-user "$DATABASE_USER" \
  --db-password "$DATABASE_PASSWORD" \
  --db-host "$DATABASE_HOST" \
  --db-port "$DATABASE_PORT" \
  --git-repo "$GIT_REPO" \
  --project-name "$PROJECT_NAME" \
  --domain "$DOMAIN" \
  --admin-email "$ADMIN_EMAIL"