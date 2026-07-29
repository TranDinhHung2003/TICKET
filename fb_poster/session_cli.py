"""CLI cho chế độ session (không cần developer account)."""

import json
import logging
import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .session_client import FacebookSessionClient, SessionLoginError, SessionPostError

console = Console()

COOKIES_DEFAULT = "fb_cookies.json"


@click.group("session")
def session_cli():
    """Chế độ session — đăng bài không cần Facebook Developer account."""


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------

@session_cli.command("login")
@click.option("--email", prompt="Email Facebook", help="Email đăng nhập Facebook.")
@click.option(
    "--password",
    prompt="Mật khẩu",
    hide_input=True,
    help="Mật khẩu Facebook.",
)
@click.option(
    "--save-cookies",
    default=COOKIES_DEFAULT,
    show_default=True,
    help="File để lưu cookies sau khi đăng nhập.",
)
def login(email, password, save_cookies):
    """Đăng nhập Facebook và lưu cookies để dùng lại.

    \b
    Sau khi đăng nhập, cookies được lưu vào file và dùng cho các lần sau
    mà không cần nhập lại mật khẩu.
    """
    client = FacebookSessionClient()
    with console.status("Đang đăng nhập…"):
        try:
            client.login(email, password)
        except SessionLoginError as exc:
            console.print(f"\n[red]Đăng nhập thất bại:[/red] {exc}")
            sys.exit(1)

    client.save_cookies(save_cookies)
    console.print(f"[green]Đăng nhập thành công![/green] Cookies đã lưu vào [bold]{save_cookies}[/bold]")


# ---------------------------------------------------------------------------
# set-cookies
# ---------------------------------------------------------------------------

@session_cli.command("set-cookies")
@click.argument("cookie_string", metavar="COOKIE_STRING")
@click.option(
    "--save",
    default=COOKIES_DEFAULT,
    show_default=True,
    help="File lưu cookies.",
)
def set_cookies(cookie_string, save):
    """Nhập cookies thủ công từ trình duyệt (cách đơn giản nhất).

    \b
    Cách lấy COOKIE_STRING:
      1. Đăng nhập Facebook trên Chrome/Firefox (bình thường)
      2. Cài extension "Cookie-Editor" hoặc "EditThisCookie"
      3. Mở extension → chọn Export → Copy as Header String
      4. Dán chuỗi đó vào đây (trong dấu nháy đơn)

    \b
    Ví dụ:
      fb-poster session set-cookies 'c_user=123456; xs=abc123; datr=xyz...'
    """
    client = FacebookSessionClient()
    client.set_cookies_from_string(cookie_string)
    client.save_cookies(save)
    console.print(f"[green]Đã lưu cookies vào[/green] [bold]{save}[/bold]")

    # Kiểm tra nhanh
    if "c_user" in cookie_string:
        console.print("[green]✓[/green] Tìm thấy c_user — cookies có vẻ hợp lệ.")
    else:
        console.print("[yellow]⚠[/yellow] Không tìm thấy c_user trong cookies. Hãy chắc chắn bạn đã copy đúng.")


# ---------------------------------------------------------------------------
# post
# ---------------------------------------------------------------------------

@session_cli.command("post")
@click.option(
    "--cookies",
    default=COOKIES_DEFAULT,
    show_default=True,
    help="File cookies đã lưu.",
)
@click.option("-m", "--message", default=None, help="Nội dung bài đăng.")
@click.option("--message-file", default=None, metavar="FILE", help="Đọc nội dung từ file.")
@click.option("--image", default=None, metavar="FILE", help="Ảnh đính kèm (tuỳ chọn).")
@click.option(
    "--groups-file",
    default=None,
    metavar="FILE",
    help="File JSON danh sách nhóm.",
)
@click.option(
    "--group-ids",
    default=None,
    metavar="ID1,ID2,…",
    help="ID các nhóm cách nhau bằng dấu phẩy.",
)
@click.option("--delay", default=20.0, show_default=True, type=float, help="Delay giữa các bài (giây).")
@click.option("--dry-run", is_flag=True, help="Chạy thử, không đăng thật.")
@click.option("--report", default=None, metavar="FILE", help="Lưu báo cáo JSON.")
@click.option("-v", "--verbose", is_flag=True)
def post(cookies, message, message_file, image, groups_file, group_ids, delay, dry_run, report, verbose):
    """Đăng bài lên nhóm Facebook bằng session cookies.

    \b
    Ví dụ:
      # Đăng nhập trước
      fb-poster session login

      # Sau đó đăng bài
      fb-poster session post -m "Quảng cáo của tôi" --group-ids 123456,789012

      # Hoặc đọc danh sách nhóm từ file
      fb-poster session post -m "Nội dung" --groups-file groups.json
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING)

    # Resolve message
    if message_file:
        msg_text = Path(message_file).read_text(encoding="utf-8").strip()
    elif message:
        msg_text = message
    else:
        if sys.stdin.isatty():
            console.print("Nhập nội dung bài đăng (Ctrl+D để kết thúc):")
        msg_text = sys.stdin.read().strip()

    if not msg_text:
        console.print("[red]Lỗi:[/red] Nội dung bài đăng trống.")
        sys.exit(1)

    # Resolve groups
    groups: list[dict] = []
    if groups_file:
        groups.extend(json.loads(Path(groups_file).read_text(encoding="utf-8")))
    if group_ids:
        for gid in group_ids.split(","):
            gid = gid.strip()
            if gid:
                groups.append({"id": gid, "name": gid})

    if not groups:
        console.print("[red]Lỗi:[/red] Cần cung cấp --groups-file hoặc --group-ids.")
        sys.exit(1)

    # Load cookies
    if not Path(cookies).exists():
        console.print(
            f"[red]Lỗi:[/red] Không tìm thấy file cookies [bold]{cookies}[/bold].\n"
            "Chạy [bold]fb-poster session login[/bold] hoặc "
            "[bold]fb-poster session set-cookies '...'[/bold] trước."
        )
        sys.exit(1)

    client = FacebookSessionClient(cookies_file=cookies)

    console.rule("[bold blue]Facebook Group Poster — Session Mode[/bold blue]")
    console.print(f"  Số nhóm : [bold]{len(groups)}[/bold]")
    console.print(f"  Delay   : [bold]{delay}s[/bold]")
    if image:
        console.print(f"  Ảnh     : {image}")
    if dry_run:
        console.print("\n[yellow][DRY RUN] Sẽ không thực sự đăng bài.[/yellow]")
    console.rule()

    if dry_run:
        for g in groups:
            console.print(f"  [green]WOULD POST[/green] → {g.get('name', g['id'])} ({g['id']})")
        return

    results = []
    ok_count = 0
    fail_count = 0

    for idx, g in enumerate(groups):
        gid = str(g.get("id", ""))
        gname = g.get("name", gid)
        bar = f"[{idx+1}/{len(groups)}]"

        try:
            success = client.post_to_group(gid, msg_text, image_path=image)
            if success:
                ok_count += 1
                console.print(f"  {bar} [green]✓[/green] {gname} ({gid})")
                results.append({"group_id": gid, "group_name": gname, "success": True})
            else:
                raise SessionPostError("Không xác nhận được bài đăng.")
        except (SessionPostError, Exception) as exc:
            fail_count += 1
            console.print(f"  {bar} [red]✗[/red] {gname} ({gid}) — {exc}")
            results.append({"group_id": gid, "group_name": gname, "success": False, "error": str(exc)})

        if idx < len(groups) - 1:
            time.sleep(delay)

    console.rule()
    console.print(
        f"[bold]Kết quả:[/bold] [green]{ok_count} thành công[/green] / "
        f"[red]{fail_count} thất bại[/red] / {len(results)} tổng cộng"
    )

    if report:
        Path(report).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"[green]Báo cáo đã lưu vào[/green] {report}")


# ---------------------------------------------------------------------------
# list-groups
# ---------------------------------------------------------------------------

@session_cli.command("list-groups")
@click.option("--cookies", default=COOKIES_DEFAULT, show_default=True)
@click.option("--save", default=None, metavar="FILE", help="Lưu danh sách nhóm ra file JSON.")
def list_groups(cookies, save):
    """Lấy danh sách nhóm từ tài khoản (parsing trang mobile Facebook)."""
    if not Path(cookies).exists():
        console.print(f"[red]Lỗi:[/red] Không tìm thấy file cookies [bold]{cookies}[/bold].")
        sys.exit(1)

    client = FacebookSessionClient(cookies_file=cookies)

    with console.status("Đang lấy danh sách nhóm…"):
        groups = client.get_my_groups()

    if not groups:
        console.print("[yellow]Không tìm thấy nhóm nào hoặc cần đăng nhập lại.[/yellow]")
        return

    table = Table(title="Danh sách nhóm Facebook", show_lines=True)
    table.add_column("STT", justify="right", style="dim")
    table.add_column("ID Nhóm", style="cyan")
    table.add_column("Tên Nhóm", style="bold")

    for i, g in enumerate(groups, 1):
        table.add_row(str(i), g["id"], g.get("name", ""))

    console.print(table)
    console.print(f"\nTổng cộng: [bold]{len(groups)}[/bold] nhóm.")

    if save:
        Path(save).write_text(json.dumps(groups, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"[green]Đã lưu vào[/green] {save}")
