"""
License server — phát hành / xác minh token bản quyền.
Chạy:  python -m license_server.app
Admin: python -m license_server.admin create --months 1 --note "Khach A"
"""
from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import string
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, g, jsonify, request, render_template_string

# ── Cấu hình ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("LICENSE_DB", str(BASE_DIR / "licenses.db")))
ADMIN_KEY = os.environ.get("LICENSE_ADMIN_KEY", "doi-admin-key-ngay")
# URL trang liên hệ mua (hiển thị cho khách)
BUY_CONTACT = os.environ.get(
    "LICENSE_BUY_CONTACT",
    "Zalo/Telegram/Facebook của bạn — điền vào biến LICENSE_BUY_CONTACT",
)
APP_NAME = "Facebook Group Poster"

SCHEMA = """
CREATE TABLE IF NOT EXISTS licenses (
    token           TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    expires_at      TEXT NOT NULL,
    duration_label  TEXT NOT NULL,
    note            TEXT DEFAULT '',
    revoked         INTEGER NOT NULL DEFAULT 0,
    machine_id      TEXT,
    machine_name    TEXT,
    first_ip        TEXT,
    last_ip         TEXT,
    activated_at    TEXT,
    last_seen_at    TEXT,
    activate_count  INTEGER NOT NULL DEFAULT 0,
    blocked_machine_id TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_licenses_machine ON licenses(machine_id);
"""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def generate_token() -> str:
    """FBP-XXXX-XXXX-XXXX-XXXX"""
    alphabet = string.ascii_uppercase + string.digits
    parts = ["".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(4)]
    return "FBP-" + "-".join(parts)


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.executescript(SCHEMA)
        # Migrate DB cũ
        cols = {
            r[1]
            for r in conn.execute("PRAGMA table_info(licenses)").fetchall()
        }
        if "blocked_machine_id" not in cols:
            conn.execute(
                "ALTER TABLE licenses ADD COLUMN blocked_machine_id TEXT DEFAULT ''"
            )


def create_license(
    *,
    days: int = 0,
    months: int = 0,
    years: int = 0,
    note: str = "",
    token: str | None = None,
) -> dict:
    if days <= 0 and months <= 0 and years <= 0:
        days = 30
    now = _utcnow()
    delta = timedelta(days=days + months * 30 + years * 365)
    expires = now + delta
    parts = []
    if years:
        parts.append(f"{years} năm")
    if months:
        parts.append(f"{months} tháng")
    if days:
        parts.append(f"{days} ngày")
    label = " + ".join(parts) if parts else "30 ngày"
    tok = token or generate_token()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO licenses(token, created_at, expires_at, duration_label, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (tok, _iso(now), _iso(expires), label, note),
        )
    return {
        "token": tok,
        "created_at": _iso(now),
        "expires_at": _iso(expires),
        "duration_label": label,
        "note": note,
    }


def _row_public(row: sqlite3.Row) -> dict:
    return {
        "token": row["token"],
        "expires_at": row["expires_at"],
        "duration_label": row["duration_label"],
        "revoked": bool(row["revoked"]),
        "activated": bool(row["machine_id"]),
        "machine_id_bound": (row["machine_id"] or "")[:12] + "…" if row["machine_id"] else None,
        "last_ip": row["last_ip"],
        "last_seen_at": row["last_seen_at"],
        "note": row["note"],
    }


def _client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or ""


def _require_admin():
    key = request.headers.get("X-Admin-Key") or request.args.get("admin_key") or ""
    if not secrets.compare_digest(key, ADMIN_KEY):
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    return None


BUY_PAGE = """
<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Mua token — {{ app_name }}</title>
  <style>
    :root { --bg:#FFF7F0; --card:#fff; --accent:#F97316; --text:#1C1917; --dim:#78716C; }
    body { margin:0; font-family:Segoe UI,system-ui,sans-serif; background:linear-gradient(160deg,#FFF7F0,#FFEDD5);
           color:var(--text); min-height:100vh; display:flex; align-items:center; justify-content:center; }
    .card { background:var(--card); border:1px solid #FED7AA; border-radius:20px; padding:36px 40px;
            max-width:520px; width:92%; box-shadow:0 12px 40px rgba(249,115,22,.12); }
    h1 { margin:0 0 8px; font-size:1.6rem; }
    .badge { display:inline-block; background:#FFEDD5; color:#C2410C; padding:4px 10px; border-radius:999px; font-size:.8rem; font-weight:600; }
    p { color:var(--dim); line-height:1.55; }
    ul { color:var(--text); line-height:1.7; }
    .contact { background:#FFF7F0; border-radius:14px; padding:16px 18px; border:1px dashed #FDBA74; margin-top:18px; }
    .contact strong { color:var(--accent); }
    code { background:#FFEDD5; padding:2px 6px; border-radius:6px; }
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">Bản quyền phần mềm</div>
    <h1>{{ app_name }}</h1>
    <p>Tải app xong bạn cần <b>mã token</b> để kích hoạt. Mỗi token chỉ dùng được <b>1 máy</b>, có thời hạn theo gói bạn mua.</p>
    <ul>
      <li>1 token ↔ 1 máy (khoá theo mã máy)</li>
      <li>Server lưu IP lần kích hoạt / lần dùng gần nhất</li>
      <li>Hết hạn theo tháng / ngày — gia hạn bằng token mới</li>
    </ul>
    <div class="contact">
      <div>Liên hệ mua token:</div>
      <strong>{{ contact }}</strong>
      <p style="margin:10px 0 0;font-size:.9rem">Sau khi thanh toán, bạn nhận mã dạng <code>FBP-XXXX-XXXX-XXXX-XXXX</code> — dán vào app để kích hoạt.</p>
    </div>
  </div>
</body>
</html>
"""


def create_app() -> Flask:
    init_db()
    app = Flask(__name__)

    @app.get("/")
    def buy_page():
        return render_template_string(
            BUY_PAGE, app_name=APP_NAME, contact=BUY_CONTACT
        )

    @app.get("/api/v1/health")
    def health():
        return jsonify({"ok": True, "service": "fb-poster-license", "time": _iso(_utcnow())})

    @app.post("/api/v1/activate")
    def activate():
        data = request.get_json(silent=True) or {}
        token = (data.get("token") or "").strip().upper()
        machine_id = (data.get("machine_id") or "").strip().lower()
        machine_name = (data.get("machine_name") or "")[:120]
        app_version = (data.get("app_version") or "")[:32]
        if not token or not machine_id or len(machine_id) < 16:
            return jsonify({"ok": False, "error": "Thiếu token hoặc machine_id"}), 400

        ip = _client_ip()
        now = _utcnow()

        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM licenses WHERE token = ?", (token,)
            ).fetchone()
            if not row:
                return jsonify({"ok": False, "error": "Token không tồn tại"}), 404
            if row["revoked"]:
                return jsonify({
                    "ok": False,
                    "error": "Token đã bị thu hồi",
                    "code": "revoked",
                }), 403
            exp = _parse_iso(row["expires_at"])
            if now >= exp:
                return jsonify({
                    "ok": False,
                    "error": "Token đã hết hạn",
                    "expires_at": row["expires_at"],
                    "code": "expired",
                }), 403

            blocked = (row["blocked_machine_id"] or "").strip().lower()
            if blocked and blocked == machine_id:
                return jsonify({
                    "ok": False,
                    "error": (
                        "Máy này đã bị gỡ khỏi token (admin reset).\n"
                        "Không thể kích hoạt lại trên máy cũ. "
                        "Dùng máy mới hoặc nhận token khác."
                    ),
                    "code": "machine_blocked",
                }), 403

            bound = row["machine_id"]
            if bound and bound != machine_id:
                return jsonify({
                    "ok": False,
                    "error": (
                        "Token đã kích hoạt trên máy khác.\n"
                        "Mỗi token chỉ dùng được 1 máy. Liên hệ admin để reset."
                    ),
                    "bound_hint": (bound[:8] + "…"),
                    "code": "bound_other",
                }), 403

            first_ip = row["first_ip"] or ip
            # Kích hoạt máy mới → xoá blocked nếu khác máy bị block
            conn.execute(
                """
                UPDATE licenses SET
                    machine_id = ?,
                    machine_name = ?,
                    first_ip = ?,
                    last_ip = ?,
                    activated_at = ?,
                    last_seen_at = ?,
                    activate_count = activate_count + 1,
                    blocked_machine_id = CASE
                        WHEN blocked_machine_id = ? THEN blocked_machine_id
                        ELSE blocked_machine_id
                    END
                WHERE token = ?
                """,
                (
                    machine_id,
                    machine_name,
                    first_ip,
                    ip,
                    _iso(now) if not bound else (row["activated_at"] or _iso(now)),
                    _iso(now),
                    machine_id,
                    token,
                ),
            )

        return jsonify({
            "ok": True,
            "message": "Kích hoạt thành công",
            "token": token,
            "expires_at": row["expires_at"],
            "duration_label": row["duration_label"],
            "machine_id": machine_id,
            "ip": ip,
            "app_version": app_version,
        })

    @app.post("/api/v1/verify")
    def verify():
        data = request.get_json(silent=True) or {}
        token = (data.get("token") or "").strip().upper()
        machine_id = (data.get("machine_id") or "").strip().lower()
        if not token or not machine_id:
            return jsonify({"ok": False, "error": "Thiếu token hoặc machine_id"}), 400

        ip = _client_ip()
        now = _utcnow()

        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM licenses WHERE token = ?", (token,)
            ).fetchone()
            if not row:
                return jsonify({
                    "ok": False, "error": "Token không tồn tại", "code": "not_found",
                }), 404
            if row["revoked"]:
                return jsonify({
                    "ok": False,
                    "error": "Token đã bị thu hồi",
                    "code": "revoked",
                }), 403
            exp = _parse_iso(row["expires_at"])
            if now >= exp:
                return jsonify({
                    "ok": False,
                    "error": "Token đã hết hạn",
                    "expires_at": row["expires_at"],
                    "code": "expired",
                }), 403

            blocked = (row["blocked_machine_id"] or "").strip().lower()
            if blocked and blocked == machine_id:
                return jsonify({
                    "ok": False,
                    "error": "Máy này đã bị gỡ khỏi token — không dùng được nữa",
                    "code": "machine_blocked",
                }), 403

            if not row["machine_id"]:
                # Đã reset — máy cũ/mới đều phải kích hoạt lại thủ công
                return jsonify({
                    "ok": False,
                    "error": "Token chưa gắn máy — cần kích hoạt lại",
                    "code": "need_activate",
                    "need_activate": True,
                }), 403

            if row["machine_id"] != machine_id:
                return jsonify({
                    "ok": False,
                    "error": "Token không khớp máy này (đã gắn máy khác)",
                    "code": "bound_other",
                }), 403

            conn.execute(
                "UPDATE licenses SET last_ip = ?, last_seen_at = ? WHERE token = ?",
                (ip, _iso(now), token),
            )

        days_left = max(0, (exp - now).days)
        return jsonify({
            "ok": True,
            "expires_at": row["expires_at"],
            "duration_label": row["duration_label"],
            "days_left": days_left,
            "ip": ip,
            "machine_name": row["machine_name"],
        })

    # ── Admin APIs ────────────────────────────────────────────────────────
    @app.post("/api/v1/admin/create")
    def admin_create():
        deny = _require_admin()
        if deny:
            return deny
        data = request.get_json(silent=True) or {}
        try:
            lic = create_license(
                days=int(data.get("days") or 0),
                months=int(data.get("months") or 0),
                years=int(data.get("years") or 0),
                note=str(data.get("note") or ""),
            )
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, "license": lic})

    @app.get("/api/v1/admin/list")
    def admin_list():
        deny = _require_admin()
        if deny:
            return deny
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM licenses ORDER BY created_at DESC LIMIT 500"
            ).fetchall()
        return jsonify({"ok": True, "items": [_row_public(r) for r in rows]})

    @app.post("/api/v1/admin/revoke")
    def admin_revoke():
        deny = _require_admin()
        if deny:
            return deny
        data = request.get_json(silent=True) or {}
        token = (data.get("token") or "").strip().upper()
        with get_db() as conn:
            # Thu hồi + chặn luôn máy đang gắn
            row = conn.execute(
                "SELECT machine_id FROM licenses WHERE token = ?", (token,)
            ).fetchone()
            if not row:
                return jsonify({"ok": False, "error": "Không tìm thấy token"}), 404
            mid = row["machine_id"] or ""
            conn.execute(
                """
                UPDATE licenses SET
                    revoked = 1,
                    blocked_machine_id = CASE
                        WHEN ? != '' THEN ?
                        ELSE blocked_machine_id
                    END
                WHERE token = ?
                """,
                (mid, mid, token),
            )
        return jsonify({"ok": True, "message": f"Đã thu hồi {token}"})

    @app.post("/api/v1/admin/reset-machine")
    def admin_reset_machine():
        """Gỡ máy cũ + chặn máy đó kích hoạt lại; chỉ máy mới được gắn."""
        deny = _require_admin()
        if deny:
            return deny
        data = request.get_json(silent=True) or {}
        token = (data.get("token") or "").strip().upper()
        with get_db() as conn:
            row = conn.execute(
                "SELECT machine_id FROM licenses WHERE token = ?", (token,)
            ).fetchone()
            if not row:
                return jsonify({"ok": False, "error": "Không tìm thấy token"}), 404
            old = row["machine_id"] or ""
            conn.execute(
                """
                UPDATE licenses SET
                    blocked_machine_id = CASE WHEN ? != '' THEN ? ELSE blocked_machine_id END,
                    machine_id = NULL,
                    machine_name = NULL,
                    activated_at = NULL
                WHERE token = ?
                """,
                (old, old, token),
            )
        return jsonify({
            "ok": True,
            "message": (
                f"Đã reset máy cho {token}. "
                "Máy cũ bị chặn; chỉ máy mới kích hoạt được."
            ),
        })

    return app

app = create_app()


def main():
    host = os.environ.get("LICENSE_HOST", "0.0.0.0")
    port = int(os.environ.get("LICENSE_PORT", "8787"))
    print(f"License server: http://{host}:{port}")
    print(f"DB: {DB_PATH}")
    print(f"Admin key: {ADMIN_KEY[:4]}… (đổi bằng LICENSE_ADMIN_KEY)")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
