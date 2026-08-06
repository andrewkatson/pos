#!/bin/bash

###############################################################################
# deploy-web.sh
#
# Build the Vite SPA and publish it to the S3 bucket that backs the website's
# CloudFront distribution, then invalidate the CDN cache so viewers get the new
# build immediately.
#
# Topology:
#   smiling.social / www  ->  CloudFront (EMS8KP5TZ1KB3)  ->  S3 (smiling-social-web)
#
# Two pieces of distribution config this script does NOT manage, both needed for
# shared post links (issue #381) — the script checks the first and warns:
#
#   1. SPA routing. /post/<id> is a client-side route with no object behind it
#      in S3, so the distribution needs custom error responses mapping 403 and
#      404 to /index.html with a 200, or a cold load of a shared link 404s.
#
#   2. Link previews. cloudfront/link-preview.js must be published as a
#      CloudFront Function and associated with the default cache behavior on
#      *viewer request*, so crawlers fetching /post/<id> are redirected to the
#      backend's Open Graph document instead of the empty SPA shell.
#
# Mobile deep linking (issue #382) needs the /.well-known/ files this script
# publishes explicitly (see below). The Android one needs the release signing
# fingerprint in ANDROID_SHA256_CERT_FINGERPRINTS.
#
# Run from a machine with the AWS CLI + Node installed and credentials that can
# write the bucket and create invalidations (s3:PutObject/DeleteObject/ListBucket
# on the bucket, cloudfront:CreateInvalidation on the distribution). Works in CI
# or locally (Git Bash on Windows is fine).
#
# Usage:
#   ./deploy-web.sh \
#     [--bucket smiling-social-web] \
#     [--distribution-id EMS8KP5TZ1KB3] \
#     [--api-base-url https://api.smiling.social/user_index] \
#     [--skip-invalidation]
###############################################################################

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
print_status()  { echo -e "${GREEN}==>${NC} $1"; }
print_error()   { echo -e "${RED}ERROR:${NC} $1"; }
print_warning() { echo -e "${YELLOW}WARNING:${NC} $1"; }

# Defaults (the current production website distribution + origin).
BUCKET="smiling-social-web"
DISTRIBUTION_ID="EMS8KP5TZ1KB3"
API_BASE_URL="https://api.smiling.social/user_index"
SKIP_INVALIDATION="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        --bucket)             BUCKET="$2"; shift 2 ;;
        --distribution-id)    DISTRIBUTION_ID="$2"; shift 2 ;;
        --api-base-url)       API_BASE_URL="$2"; shift 2 ;;
        --skip-invalidation)  SKIP_INVALIDATION="true"; shift ;;
        --help)
            grep '^#' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) print_error "Unknown option: $1"; exit 1 ;;
    esac
done

# Run from the website/ dir regardless of where the script was invoked.
cd "$(dirname "$0")"

command -v aws  > /dev/null 2>&1 || { print_error "aws CLI not found on PATH."; exit 1; }
command -v node > /dev/null 2>&1 || { print_error "node not found on PATH (need Node 20+ for Vite)."; exit 1; }

print_status "Installing dependencies (npm ci)..."
npm ci

print_status "Building SPA with VITE_API_BASE_URL=$API_BASE_URL ..."
# Web push (issues #342/#343) is opt-in: export the VITE_FIREBASE_* vars (public
# Firebase Web config + VAPID key) in the deploy environment to enable it. When
# they are unset the build still succeeds and push is simply a no-op client-side.
VITE_API_BASE_URL="$API_BASE_URL" \
  VITE_FIREBASE_API_KEY="${VITE_FIREBASE_API_KEY:-}" \
  VITE_FIREBASE_AUTH_DOMAIN="${VITE_FIREBASE_AUTH_DOMAIN:-}" \
  VITE_FIREBASE_PROJECT_ID="${VITE_FIREBASE_PROJECT_ID:-}" \
  VITE_FIREBASE_MESSAGING_SENDER_ID="${VITE_FIREBASE_MESSAGING_SENDER_ID:-}" \
  VITE_FIREBASE_APP_ID="${VITE_FIREBASE_APP_ID:-}" \
  VITE_FIREBASE_VAPID_KEY="${VITE_FIREBASE_VAPID_KEY:-}" \
  npm run build

if [ ! -d dist ]; then
    print_error "Build did not produce a dist/ directory."
    exit 1
fi

# Sync to S3 in two passes so each file's Cache-Control matches its cacheability:
#  1) Vite's /assets/* are content-hashed (fingerprinted), so cache them forever.
#  2) Everything else (index.html, favicon.svg, robots.txt, ...) is NOT
#     fingerprinted and must revalidate — otherwise a redeploy can't dislodge a
#     stale cached copy (e.g. an old favicon lingering for up to a year).
# --delete in pass 1 prunes only within assets/; pass 2 excludes assets/ so it
# prunes the rest without deleting what pass 1 just uploaded.
print_status "Syncing fingerprinted assets to s3://$BUCKET/assets/ (immutable)..."
aws s3 sync dist/assets/ "s3://$BUCKET/assets/" --delete \
    --cache-control "public,max-age=31536000,immutable"

print_status "Syncing the rest to s3://$BUCKET/ (no-cache)..."
# .well-known/ is excluded here and uploaded below instead. Two reasons: those
# files need an explicit application/json content type (the AASA has no
# extension, so sync would guess binary/octet-stream and iOS would reject it),
# and --delete would otherwise remove a previously published assetlinks.json on
# any deploy that runs without the Android signing fingerprint configured.
aws s3 sync dist/ "s3://$BUCKET/" --delete --exclude "assets/*" --exclude ".well-known/*" \
    --cache-control "no-cache"

# ---------------------------------------------------------------------------
# Mobile deep linking (issue #382)
# ---------------------------------------------------------------------------
# iOS Universal Links and Android App Links are both claimed by a file under
# /.well-known/, fetched by the OS at install time. Both must be served as
# application/json, over https, with no redirect.
print_status "Publishing /.well-known/apple-app-site-association ..."
aws s3 cp dist/.well-known/apple-app-site-association \
    "s3://$BUCKET/.well-known/apple-app-site-association" \
    --content-type "application/json" --cache-control "public,max-age=3600"

# assetlinks.json needs the release signing certificate's SHA-256 fingerprint,
# which is not in the repo (Play App Signing holds it — read it from Play
# Console > Setup > App integrity). Export it to enable Android App Links:
#
#   ANDROID_SHA256_CERT_FINGERPRINTS="AB:CD:...:EF" ./deploy-web.sh
#
# Comma-separate several to serve more than one signing key (e.g. while
# migrating, or to also accept a local debug key). When unset the file is left
# alone rather than published half-configured: a wrong fingerprint fails
# verification silently and links quietly stop opening the app.
if [ -n "${ANDROID_SHA256_CERT_FINGERPRINTS:-}" ]; then
    print_status "Publishing /.well-known/assetlinks.json ..."
    FINGERPRINT_JSON="$(printf '%s' "$ANDROID_SHA256_CERT_FINGERPRINTS" \
        | awk -F, '{for (i=1;i<=NF;i++){gsub(/^[ \t]+|[ \t]+$/,"",$i); printf "%s\"%s\"", (i>1?", ":""), $i}}')"
    cat > dist/.well-known/assetlinks.json <<EOF
[
  {
    "relation": ["delegate_permission/common.handle_all_urls"],
    "target": {
      "namespace": "android_app",
      "package_name": "${ANDROID_PACKAGE_NAME:-io.github.andrewkatson.positiveonlysocial}",
      "sha256_cert_fingerprints": [$FINGERPRINT_JSON]
    }
  }
]
EOF
    aws s3 cp dist/.well-known/assetlinks.json "s3://$BUCKET/.well-known/assetlinks.json" \
        --content-type "application/json" --cache-control "public,max-age=3600"
else
    print_warning "ANDROID_SHA256_CERT_FINGERPRINTS is unset; leaving /.well-known/assetlinks.json untouched. Android App Links will not verify until it is published."
fi

# A shared /post/<id> link is a client-side route with nothing behind it in S3,
# so CloudFront must rewrite the resulting 403/404 to /index.html with a 200 or
# a cold load of the link fails (issue #381). Only a warning: the check needs
# cloudfront:GetDistributionConfig, which a deploy role may not carry, and a
# missing permission must not fail an otherwise good deploy.
print_status "Checking SPA routing (403/404 -> /index.html) on $DISTRIBUTION_ID ..."
SPA_ERRORS="$(aws cloudfront get-distribution-config --id "$DISTRIBUTION_ID" \
    --query "DistributionConfig.CustomErrorResponses.Items[?ResponsePagePath=='/index.html' && ResponseCode=='200'].ErrorCode" \
    --output text 2>/dev/null || true)"
for code in 403 404; do
    case " $SPA_ERRORS " in
        *" $code "*) ;;
        *) print_warning "No custom error response maps $code -> /index.html (200). A cold load of https://smiling.social/post/<id> will fail until one is added." ;;
    esac
done

if [ "$SKIP_INVALIDATION" = "true" ]; then
    print_warning "Skipping CloudFront invalidation (--skip-invalidation)."
else
    print_status "Invalidating CloudFront distribution $DISTRIBUTION_ID ..."
    aws cloudfront create-invalidation \
        --distribution-id "$DISTRIBUTION_ID" \
        --paths "/*" \
        --query "Invalidation.Id" --output text
fi

print_status "Website deployed. https://smiling.social should reflect the new build shortly."
