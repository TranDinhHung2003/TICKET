#!/bin/bash
cd "$(dirname "$0")"
export LICENSE_ADMIN_KEY="${LICENSE_ADMIN_KEY:-doi-admin-key-ngay}"
export LICENSE_PORT="${LICENSE_PORT:-8787}"
export LICENSE_BUY_CONTACT="${LICENSE_BUY_CONTACT:-Zalo/Telegram — điền liên hệ của bạn}"
pip3 install flask requests -q
python3 -m license_server
