#!/bin/bash
set -e

apt-get update
apt-get install -y python3 python3-pip python3-venv python3-websockets python3-cryptography

mkdir -p /opt/app-ff
cd /opt/app-ff

cat << 'EOF' > server_websocket.py
${PYTHON_CODE}
EOF

cat << 'EOF' > /etc/systemd/system/websocket-backend.service
[Unit]
Description=Python WebSocket / HTTP server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/app-ff
ExecStart=/usr/bin/python3 server_websocket.py
Restart=always
RestartSec=5
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=websocket-backend

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable websocket-backend.service
systemctl start websocket-backend.service
