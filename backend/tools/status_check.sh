#!/bin/bash

echo "=== Checking Gunicorn ==="
sudo systemctl status gunicorn --no-pager

echo -e "\n=== Checking Nginx ==="
sudo systemctl status nginx --no-pager

echo -e "\n=== Checking Socket ==="
ls -l /var/www/smiling-social/gunicorn.sock

echo -e "\n=== Checking Nginx Ports ==="
sudo netstat -tlnp | grep nginx

echo -e "\n=== Recent Gunicorn Logs ==="
sudo journalctl -u gunicorn -n 10 --no-pager

echo -e "\n=== Testing Local Connection ==="
curl -I http://localhost 2>/dev/null | head -n 1

echo -e "\n=== Testing HTTPS ==="
curl -I https://smiling.social 2>/dev/null | head -n 1