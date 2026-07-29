"""
CLI quản lý token bản quyền.

Ví dụ:
  python -m license_server.admin create --minutes 1 --note "Thu 1 phut"
  python -m license_server.admin create --hours 2 --note "Thu 2 gio"
  python -m license_server.admin create --months 1 --note "Khach Nam"
  python -m license_server.admin create --days 7 --note "Dung thu"
  python -m license_server.admin list
  python -m license_server.admin revoke FBP-XXXX-XXXX-XXXX-XXXX
  python -m license_server.admin reset FBP-XXXX-XXXX-XXXX-XXXX
"""
from __future__ import annotations

import argparse
import json
import sys

from license_server.app import (
    create_license,
    get_db,
    init_db,
)


def cmd_create(args):
    init_db()
    lic = create_license(
        minutes=args.minutes,
        hours=args.hours,
        days=args.days,
        months=args.months,
        years=args.years,
        note=args.note or "",
    )
    print("=" * 50)
    print("TOKEN MỚI — gửi cho khách:")
    print(lic["token"])
    print("=" * 50)
    print(f"Thời hạn : {lic['duration_label']}")
    print(f"Hết hạn  : {lic['expires_at']}")
    print(f"Ghi chú  : {lic['note'] or '(không)'}")
    print()
    print(json.dumps(lic, ensure_ascii=False, indent=2))


def cmd_list(_args):
    init_db()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM licenses ORDER BY created_at DESC LIMIT 200"
        ).fetchall()
    if not rows:
        print("(chưa có token)")
        return
    for r in rows:
        status = "REVOKED" if r["revoked"] else ("OK" if r["machine_id"] else "UNUSED")
        mid = (r["machine_id"] or "-")[:10]
        print(
            f"{r['token']}  [{status}]  hết:{r['expires_at'][:10]}  "
            f"máy:{mid}  ip:{r['last_ip'] or '-'}  note:{r['note'] or ''}"
        )


def cmd_revoke(args):
    init_db()
    token = args.token.strip().upper()
    with get_db() as conn:
        row = conn.execute(
            "SELECT machine_id FROM licenses WHERE token = ?", (token,)
        ).fetchone()
        if not row:
            print("Không tìm thấy token", file=sys.stderr)
            sys.exit(1)
        mid = row["machine_id"] or ""
        conn.execute(
            """
            UPDATE licenses SET
                revoked = 1,
                blocked_machine_id = CASE WHEN ? != '' THEN ? ELSE blocked_machine_id END
            WHERE token = ?
            """,
            (mid, mid, token),
        )
    print(f"Đã thu hồi {token} — máy cũ bị chặn ngay khi online lại")


def cmd_reset(args):
    init_db()
    token = args.token.strip().upper()
    with get_db() as conn:
        row = conn.execute(
            "SELECT machine_id FROM licenses WHERE token = ?", (token,)
        ).fetchone()
        if not row:
            print("Không tìm thấy token", file=sys.stderr)
            sys.exit(1)
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
    print(
        f"Đã reset {token}\n"
        f"- Máy cũ bị CHẶN (không kích hoạt lại được)\n"
        f"- Máy MỚI của khách mới kích hoạt được"
    )


def cmd_show(args):
    init_db()
    token = args.token.strip().upper()
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM licenses WHERE token = ?", (token,)
        ).fetchone()
    if not row:
        print("Không tìm thấy", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(dict(row), ensure_ascii=False, indent=2))


def main(argv=None):
    p = argparse.ArgumentParser(description="Quản lý token bản quyền FB Poster")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create", help="Tạo token mới")
    c.add_argument("--minutes", type=int, default=0, help="Số phút (vd: 1 = dùng thử 1 phút)")
    c.add_argument("--hours", type=int, default=0, help="Số giờ")
    c.add_argument("--days", type=int, default=0)
    c.add_argument("--months", type=int, default=0)
    c.add_argument("--years", type=int, default=0)
    c.add_argument("--note", default="")
    c.set_defaults(func=cmd_create)

    l = sub.add_parser("list", help="Liệt kê token")
    l.set_defaults(func=cmd_list)

    r = sub.add_parser("revoke", help="Thu hồi token")
    r.add_argument("token")
    r.set_defaults(func=cmd_revoke)

    rs = sub.add_parser("reset", help="Reset máy gắn với token")
    rs.add_argument("token")
    rs.set_defaults(func=cmd_reset)

    s = sub.add_parser("show", help="Chi tiết 1 token")
    s.add_argument("token")
    s.set_defaults(func=cmd_show)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
