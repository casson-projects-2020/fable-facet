#!/bin/bash

clear
pip install flask --user -q

python3 tutorial.py &

sleep 2

WEB_URL=$(cloudshell get-web-preview-url --port 8080)

clear 

echo ""
echo "===================================================="
echo "  FABLE FACET WIZARD READY "
echo "  Click on the link below to see the wizard"
echo "  $WEB_URL"
echo "===================================================="
echo ""
