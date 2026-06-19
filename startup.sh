#!/bin/bash
apt-get update
apt-get install -y python3-venv python3-pip git nginx certbot python3-certbot-nginx sqlite3
mkdir -p /opt/thronesbot
chown -R ubuntu:ubuntu /opt/thronesbot
