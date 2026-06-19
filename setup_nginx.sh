#!/bin/bash
cat << 'CONF' > /etc/nginx/sites-available/thronesbot
server {
    listen 80;
    server_name 34.10.254.83.nip.io;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
CONF
ln -sf /etc/nginx/sites-available/thronesbot /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
systemctl restart nginx
certbot --nginx -d 34.10.254.83.nip.io --non-interactive --agree-tos -m admin@34.10.254.83.nip.io
