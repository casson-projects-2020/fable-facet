#!/bin/bash

sudo apt install dialog

(
    pip install flask --user -q

    fuser -k 8080/tcp > /dev/null 2>&1

    pip install --upgrade pip
    pip install google-genai

    if pgrep -f "[y]fc_server.py" > /dev/null; then
        echo "server already running"
    else
        python3 yfc_server.py &
    fi

    sleep 5

    perl -e 'ioctl(STDIN, 0x5412, $_) for split //, "\n"'

) | dialog --programbox "Initializing, please wait..." 20 80 && clear


WEB_URL=$(cloudshell get-web-preview-url --port 8080)

timeout --foreground 30s dialog --cr-wrap --programbox "App running.\n\n\
Click on the link to open it:\n\n\
$WEB_URL" 10 100 || clear
