"""
License client — kích hoạt / xác minh token trên máy người dùng.
Khoá theo machine_id (HWID). Server lưu IP để theo dõi.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
import time
import uuid
from pathlib import Path

import requests

DEFAULT_SERVER = os.environ.get(
    "FB_LICENSE_SERVER",
    "http://127.0.0.1:8787",
)

DATA_DIR = Path.home() / ".fb_poster"
LICENSE_FILE = DATA_DIR / "license.json"
CONFIG_FILE = DATA_DIR / "license_config.json"

# Offline chỉ khi MẤT MẠNG — và rất ngắn (sau revoke/reset phải online)
OFFLINE_GRACE_HOURS = float(os.environ.get("FB_LICENSE_OFFLINE_HOURS", "6"))


def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_server_url() -> str:
    _ensure_dir()
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            url = (data.get("server_url") or "").strip().rstrip("/")
            if url:
                return url
        except Exception:
            pass
    return DEFAULT_SERVER.rstrip("/")


def set_server_url(url: str) -> None:
    _ensure_dir()
    data = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}
    data["server_url"] = url.strip().rstrip("/")
    CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_machine_id() -> str:
    """
    Mã máy ổn định (không dùng IP làm khoá chính — IP hay đổi).
    Hash SHA256 các thành phần phần cứng / OS.
    """
    parts = [
        platform.system(),
        platform.machine(),
        platform.node(),
        str(uuid.getnode()),
    ]
    try:
        if platform.system() == "Windows":
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
            )
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            parts.append(str(guid))
    except Exception:
        pass
    try:
        mid = Path("/etc/machine-id")
        if mid.is_file():
            parts.append(mid.read_text(encoding="utf-8").strip())
    except Exception:
        pass

    raw = "|".join(parts).encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()


def get_machine_name() -> str:
    try:
        return socket.gethostname()[:120]
    except Exception:
        return platform.node()[:120]


def load_local_license() -> dict | None:
    _ensure_dir()
    if not LICENSE_FILE.exists():
        return None
    try:
        data = json.loads(LICENSE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("token"):
            return data
    except Exception:
        pass
    return None


def save_local_license(data: dict) -> None:
    _ensure_dir()
    payload = {
        "token": data.get("token"),
        "expires_at": data.get("expires_at"),
        "duration_label": data.get("duration_label"),
        "machine_id": data.get("machine_id") or get_machine_id(),
        "activated_at": data.get("activated_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "last_verify_at": time.time(),
        "server_url": get_server_url(),
    }
    LICENSE_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def clear_local_license() -> None:
    try:
        if LICENSE_FILE.exists():
            LICENSE_FILE.unlink()
    except Exception:
        pass


def activate(token: str, timeout: float = 15.0) -> tuple[bool, str, dict]:
    """Kích hoạt token trên máy này."""
    token = (token or "").strip().upper()
    if not token.startswith("FBP-"):
        return False, "Token không đúng định dạng (FBP-XXXX-…)", {}

    mid = get_machine_id()
    url = get_server_url() + "/api/v1/activate"
    try:
        r = requests.post(
            url,
            json={
                "token": token,
                "machine_id": mid,
                "machine_name": get_machine_name(),
                "app_version": os.environ.get("FB_APP_VERSION", ""),
            },
            timeout=timeout,
        )
        data = r.json() if r.content else {}
    except requests.exceptions.ConnectionError:
        return False, (
            f"Không kết nối được server license:\n{get_server_url()}\n"
            "Kiểm tra mạng hoặc hỏi admin URL server."
        ), {}
    except Exception as exc:
        return False, f"Lỗi kích hoạt: {exc}", {}

    if not data.get("ok"):
        # Thu hồi / chặn máy → xoá cache local
        code = data.get("code") or ""
        if code in ("revoked", "expired", "machine_blocked", "bound_other"):
            clear_local_license()
        return False, data.get("error") or f"HTTP {r.status_code}", data

    save_local_license({
        "token": data.get("token") or token,
        "expires_at": data.get("expires_at"),
        "duration_label": data.get("duration_label"),
        "machine_id": mid,
    })
    return True, data.get("message") or "Kích hoạt thành công", data


def verify(
    timeout: float = 12.0,
    allow_offline_hours: float | None = None,
) -> tuple[bool, str, dict]:
    """
    Xác minh token còn hạn + đúng máy.
    - Server trả lỗi (revoked/reset/…) → XOÁ license local ngay.
    - Không tự activate lại (tránh máy cũ sau reset tự vào lại).
    - Offline chỉ khi mất mạng và trong thời gian grace ngắn.
    """
    if allow_offline_hours is None:
        allow_offline_hours = OFFLINE_GRACE_HOURS

    local = load_local_license()
    if not local:
        return False, "Chưa kích hoạt bản quyền — nhập token để tiếp tục", {}

    mid = get_machine_id()
    if local.get("machine_id") and local["machine_id"] != mid:
        clear_local_license()
        return False, "License không khớp máy này — đã xoá bản quyền local", {}

    url = get_server_url() + "/api/v1/verify"
    try:
        r = requests.post(
            url,
            json={"token": local["token"], "machine_id": mid},
            timeout=timeout,
        )
        data = r.json() if r.content else {}
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        last = float(local.get("last_verify_at") or 0)
        age_h = (time.time() - last) / 3600 if last else 9999
        if last and age_h <= allow_offline_hours:
            return True, (
                f"Offline tạm ({age_h:.0f}h) — cần online sớm. "
                f"Grace {allow_offline_hours:.0f}h."
            ), local
        return False, f"Không xác minh được (cần mạng): {exc}", local
    except Exception as exc:
        return False, f"Lỗi xác minh: {exc}", local

    # Server đã trả lời — không dùng offline cache khi bị từ chối
    if not data.get("ok"):
        code = data.get("code") or ""
        err = data.get("error") or "License không hợp lệ"
        # Mọi từ chối từ server → xoá local (revoked / reset / hết hạn / sai máy)
        clear_local_license()
        if code == "need_activate" or data.get("need_activate"):
            return False, (
                "Token đã bị gỡ máy / chưa gắn máy.\n"
                "Nhập lại token trên máy ĐƯỢC PHÉP (máy mới sau reset)."
            ), data
        return False, err, data

    local["expires_at"] = data.get("expires_at") or local.get("expires_at")
    local["duration_label"] = data.get("duration_label") or local.get("duration_label")
    local["last_verify_at"] = time.time()
    local["days_left"] = data.get("days_left")
    save_local_license(local)
    days = data.get("days_left")
    extra = f" — còn ~{days} ngày" if days is not None else ""
    return True, f"License OK{extra}", {**local, **data}


def status_summary() -> str:
    local = load_local_license()
    if not local:
        return "Chưa kích hoạt"
    exp = local.get("expires_at") or "?"
    days = local.get("days_left")
    if days is not None:
        return f"Token …{local['token'][-4:]} | hết {exp[:10]} | còn ~{days} ngày"
    return f"Token …{local['token'][-4:]} | hết hạn {exp[:10]}"
