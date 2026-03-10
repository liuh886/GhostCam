#!/bin/bash
# GhostCam Management Script for Linux
# Usage: ./GhostCam.sh [start|stop|setup|install-driver]

ACTION=${1:-start}
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$SCRIPT_DIR/.venv"

function show_banner {
    echo -e "\e[36m👻 GhostCam (Headless-VCam) Control\e[0m"
    echo "------------------------------------"
}

function setup_env {
    echo -e "\e[33m[*] Installing system dependencies (Ubuntu/Debian)...\e[0m"
    sudo apt-get update && sudo apt-get install -y python3-venv python3-pip ffmpeg v4l2loopback-utils
    
    echo -e "\e[33m[*] Setting up Virtual Environment...\e[0m"
    [ ! -d "$VENV_DIR" ] && python3 -m venv "$VENV_DIR"
    
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip
    pip install -r "$SCRIPT_DIR/requirements.txt"
    echo -e "\e[32m[+] Environment ready.\e[0m"
}

function install_driver {
    echo -e "\e[33m[*] Loading v4l2loopback driver...\e[0m"
    sudo modprobe v4l2loopback devices=1 video_nr=10 card_label="GhostCam" exclusive_caps=1
    echo -e "\e[32m[+] Driver loaded as /dev/video10.\e[0m"
}

function start_ghostcam {
    [ ! -d "$VENV_DIR" ] && setup_env
    source "$VENV_DIR/bin/activate"
    
    python3 "$SCRIPT_DIR/src/ghostcam/main.py" --input /dev/video0 --width 1280 --height 720
}

show_banner

case "$ACTION" in
    setup) setup_env ;;
    install-driver) install_driver ;;
    start) start_ghostcam ;;
    stop) pkill -f "ghostcam/main.py" && echo -e "\e[32m[+] Stopped.\e[0m" ;;
    *) echo "Usage: $0 {start|stop|setup|install-driver}" ;;
esac
