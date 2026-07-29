#!/bin/bash
# Script build EXE cho Linux/macOS (tạo binary native)
set -e

echo "============================================"
echo " Facebook Group Poster - Build Binary"
echo "============================================"
echo

echo "[1/3] Cài đặt dependencies..."
pip3 install -r requirements.txt -q
pip3 install pyinstaller -q

echo
echo "[2/3] Build binary..."
~/.local/bin/pyinstaller fb_poster.spec --clean --noconfirm 2>&1

echo
if [ -f "dist/FacebookGroupPoster" ]; then
    echo "[3/3] BUILD THÀNH CÔNG!"
    echo
    echo "Binary nằm tại: dist/FacebookGroupPoster"
    ls -lh dist/FacebookGroupPoster
else
    echo "[LỖI] Build thất bại."
    exit 1
fi
