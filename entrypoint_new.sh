#!/bin/bash

# Instala o Flask se não existir (necessário para o servidor)
pip install flask --user -q

# Inicia o servidor em background
python3 server.py &

# Espera 2 segundos para o servidor subir
sleep 2

# Gera a URL de preview
WEB_URL="https://8080-dot-$(cloudshell edit-info | grep 'host' | cut -d' ' -f2 | cut -d'.' -f1)-dot-devshell.appspot.com"

echo ""
echo "===================================================="
echo "  FABLE FACET WIZARD READY "
echo "  Click on the link below to see the wizard"
echo "  $WEB_URL"
echo "===================================================="
echo ""
