#!/bin/bash

clear
pip install flask --user -q

python3 tutorial.py &

sleep 2

WEB_URL="https://8080-dot-$(cloudshell edit-info | grep 'host' | cut -d' ' -f2 | cut -d'.' -f1)-dot-devshell.appspot.com"

echo ""
echo "===================================================="
echo "  FABLE FACET WIZARD READY "
echo "  Click on the link below to see the wizard"
echo "  $WEB_URL"
echo "===================================================="
echo ""
