"""Command-line interface for the Facebook Group Poster tool."""

import json
import logging
import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from .api import FacebookClient, FacebookAPIError
from .poster import GroupPoster, PostConfig

load_dotenv()
console = Console()


def _get_token(token_opt: str | None) -> str:
    token = token_opt or os.getenv("FB_ACCESS_TOKEN", "")
    if not token:
        console.print(
            "[red]Lỗi:[/red] Không tìm thấy access token.\n"
            "Đặt biến môi trường [bold]FB_ACCESS_TOKEN[/bold] hoặc dùng tùy chọn [bold]--token[/bold]."
        )
        sys.exit(1)
    return token


@click.group()
@click.version_option("1.0.0")
def cli():
    """Facebook Group Poster — Tool đăng bài quảng cáo lên các nhóm Facebook."""


# ---------------------------------------------------------------------------
# list-groups
# ---------------------------------------------------------------------------

@cli.command("list-groups")
@click.option("--token", default=None, help="Facebook User Access Token.")
@click.option("--json-output", is_flag=True, help="Xuất danh sách nhóm dưới dạng JSON.")
@click.option("--save", default=None, metavar="FILE", help="Lưu danh sách nhóm ra file (JSON).")
def list_groups(token, json_output, save):
    """Liệt kê tất cả nhóm mà tài khoản đang tham gia."""
    client = FacebookClient(_get_token(token))

    with console.status("Đang lấy danh sách nhóm…"):
        try:
            me = client.get_me()
            groups = client.get_my_groups()
        except FacebookAPIError as exc:
            console.print(f"[red]Lỗi API:[/red] {exc}")
            sys.exit(1)

    console.print(f"[green]Xin chào,[/green] {me.get('name')} ({me.get('id')})")
    console.print(f"Tìm thấy [bold]{len(groups)}[/bold] nhóm.\n")

    if json_output:
        click.echo(json.dumps(groups, ensure_ascii=False, indent=2))
    else:
        table = Table(title="Danh sách nhóm Facebook", show_lines=True)
        table.add_column("STT", justify="right", style="dim")
        table.add_column("ID Nhóm", style="cyan")
        table.add_column("Tên Nhóm", style="bold")
        table.add_column("Quyền riêng tư")

        for i, g in enumerate(groups, 1):
            privacy = g.get("privacy", "N/A")
            color = "green" if privacy == "OPEN" else "yellow"
            table.add_row(
                str(i),
                g["id"],
                g.get("name", ""),
                f"[{color}]{privacy}[/{color}]",
            )
        console.print(table)

    if save:
        Path(save).write_text(json.dumps(groups, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"\n[green]Đã lưu danh sách nhóm vào[/green] {save}")


# ---------------------------------------------------------------------------
# post
# ---------------------------------------------------------------------------

@cli.command("post")
@click.option("--token", default=None, help="Facebook User Access Token.")
@click.option(
    "--message",
    "-m",
    default=None,
    help="Nội dung bài đăng (văn bản). Nếu bỏ trống sẽ đọc từ stdin.",
)
@click.option("--message-file", default=None, metavar="FILE", help="Đọc nội dung từ file văn bản.")
@click.option("--link", default=None, help="URL đính kèm bài đăng.")
@click.option("--image", default=None, metavar="FILE", help="Đường dẫn ảnh cục bộ.")
@click.option("--image-url", default=None, help="URL ảnh từ internet.")
@click.option(
    "--groups-file",
    default=None,
    metavar="FILE",
    help="File JSON chứa danh sách nhóm (dùng output của lệnh list-groups).",
)
@click.option(
    "--group-ids",
    default=None,
    metavar="ID1,ID2,…",
    help="Danh sách ID nhóm cách nhau bằng dấu phẩy.",
)
@click.option(
    "--delay",
    default=15.0,
    show_default=True,
    type=float,
    help="Thời gian chờ giữa các lần đăng (giây).",
)
@click.option(
    "--skip-ids",
    default=None,
    metavar="ID1,ID2,…",
    help="Bỏ qua các nhóm có ID trong danh sách này.",
)
@click.option("--dry-run", is_flag=True, help="Chạy thử — không thực sự đăng bài.")
@click.option("--report", default=None, metavar="FILE", help="Lưu báo cáo kết quả ra file JSON.")
@click.option("-v", "--verbose", is_flag=True, help="Hiển thị log chi tiết.")
def post(
    token,
    message,
    message_file,
    link,
    image,
    image_url,
    groups_file,
    group_ids,
    delay,
    skip_ids,
    dry_run,
    report,
    verbose,
):
    """Đăng bài quảng cáo lên các nhóm Facebook.

    \b
    Ví dụ:
      # Đăng văn bản vào tất cả nhóm đã lưu
      fb-poster post -m "Mua ngay!" --groups-file groups.json

      # Đăng bài có ảnh và link vào một số nhóm cụ thể
      fb-poster post -m "Xem tại đây" --link https://example.com \\
          --image banner.jpg --group-ids 123456,789012

      # Chạy thử trước khi đăng thật
      fb-poster post -m "Test" --groups-file groups.json --dry-run
    """
    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
    else:
        logging.basicConfig(level=logging.WARNING)

    # Resolve message
    if message_file:
        msg_text = Path(message_file).read_text(encoding="utf-8").strip()
    elif message:
        msg_text = message
    else:
        if sys.stdin.isatty():
            console.print("Nhập nội dung bài đăng (kết thúc bằng Ctrl+D hoặc Ctrl+Z):")
        msg_text = sys.stdin.read().strip()

    if not msg_text:
        console.print("[red]Lỗi:[/red] Nội dung bài đăng không được để trống.")
        sys.exit(1)

    # Resolve groups
    groups: list[dict] = []
    if groups_file:
        raw = json.loads(Path(groups_file).read_text(encoding="utf-8"))
        groups.extend(raw)
    if group_ids:
        for gid in group_ids.split(","):
            gid = gid.strip()
            if gid:
                groups.append({"id": gid, "name": gid})

    if not groups:
        console.print(
            "[red]Lỗi:[/red] Vui lòng cung cấp danh sách nhóm qua [bold]--groups-file[/bold] "
            "hoặc [bold]--group-ids[/bold]."
        )
        sys.exit(1)

    skip_set: set[str] = set()
    if skip_ids:
        skip_set = {s.strip() for s in skip_ids.split(",")}

    config = PostConfig(
        message=msg_text,
        link=link,
        image_path=image,
        image_url=image_url,
        delay_between_posts=delay,
        skip_group_ids=skip_set,
    )

    # Summary before posting
    console.rule("[bold blue]Facebook Group Poster[/bold blue]")
    console.print(f"  Số nhóm cần đăng : [bold]{len(groups)}[/bold]")
    console.print(f"  Delay giữa bài   : [bold]{delay}s[/bold]")
    if link:
        console.print(f"  Link đính kèm    : {link}")
    if image:
        console.print(f"  Ảnh cục bộ       : {image}")
    if image_url:
        console.print(f"  URL ảnh          : {image_url}")
    if dry_run:
        console.print("\n[yellow][DRY RUN] Sẽ không thực sự đăng bài.[/yellow]\n")
    console.rule()

    if dry_run:
        for g in groups:
            gid = g.get("id", "?")
            gname = g.get("name", gid)
            if gid in skip_set:
                console.print(f"  [dim]SKIP[/dim]  {gname} ({gid})")
            else:
                console.print(f"  [green]WOULD POST[/green] → {gname} ({gid})")
        return

    client = FacebookClient(_get_token(token))
    poster = GroupPoster(client)

    success_count = 0
    fail_count = 0

    def on_progress(result, idx, total):
        nonlocal success_count, fail_count
        bar = f"[{idx}/{total}]"
        if result.success:
            success_count += 1
            console.print(
                f"  {bar} [green]✓[/green] {result.group_name} ({result.group_id}) "
                f"— post_id: {result.post_id}"
            )
        else:
            fail_count += 1
            console.print(
                f"  {bar} [red]✗[/red] {result.group_name} ({result.group_id}) "
                f"— {result.error}"
            )

    results = poster.post_to_groups(groups, config, progress_callback=on_progress)

    console.rule()
    console.print(
        f"[bold]Kết quả:[/bold] "
        f"[green]{success_count} thành công[/green] / "
        f"[red]{fail_count} thất bại[/red] / "
        f"{len(results)} tổng cộng"
    )

    if report:
        report_data = [
            {
                "group_id": r.group_id,
                "group_name": r.group_name,
                "success": r.success,
                "post_id": r.post_id,
                "error": r.error,
            }
            for r in results
        ]
        Path(report).write_text(
            json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        console.print(f"[green]Báo cáo đã lưu vào[/green] {report}")


# ---------------------------------------------------------------------------
# post-batch
# ---------------------------------------------------------------------------

@cli.command("post-batch")
@click.option("--token", default=None, help="Facebook User Access Token.")
@click.argument("campaign_file", metavar="CAMPAIGN_JSON")
@click.option("--dry-run", is_flag=True, help="Chạy thử — không thực sự đăng bài.")
@click.option("-v", "--verbose", is_flag=True)
def post_batch(token, campaign_file, dry_run, verbose):
    """Đăng nhiều chiến dịch quảng cáo từ file JSON.

    \b
    Cấu trúc CAMPAIGN_JSON:
    [
      {
        "message": "Nội dung bài đăng",
        "link": "https://example.com",        // tuỳ chọn
        "image_url": "https://img.com/a.jpg", // tuỳ chọn
        "image_path": "/path/to/img.jpg",     // tuỳ chọn
        "delay": 15,
        "groups": [
          {"id": "123456", "name": "Nhóm A"},
          {"id": "789012", "name": "Nhóm B"}
        ]
      }
    ]
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING)

    campaigns = json.loads(Path(campaign_file).read_text(encoding="utf-8"))
    client = FacebookClient(_get_token(token))
    poster = GroupPoster(client)

    total_ok = 0
    total_fail = 0

    for ci, camp in enumerate(campaigns, 1):
        console.rule(f"[bold]Chiến dịch {ci}/{len(campaigns)}[/bold]")
        console.print(f"  Nội dung: {camp['message'][:80]}…")

        groups = camp.get("groups", [])
        config = PostConfig(
            message=camp["message"],
            link=camp.get("link"),
            image_path=camp.get("image_path"),
            image_url=camp.get("image_url"),
            delay_between_posts=float(camp.get("delay", 15)),
        )

        if dry_run:
            for g in groups:
                console.print(f"  [yellow]WOULD POST[/yellow] → {g.get('name', g['id'])}")
            continue

        def on_progress(result, idx, total):
            bar = f"[{idx}/{total}]"
            if result.success:
                console.print(f"  {bar} [green]✓[/green] {result.group_name}")
            else:
                console.print(f"  {bar} [red]✗[/red] {result.group_name} — {result.error}")

        results = poster.post_to_groups(groups, config, progress_callback=on_progress)
        ok = sum(1 for r in results if r.success)
        fail = len(results) - ok
        total_ok += ok
        total_fail += fail
        console.print(f"  → [green]{ok} OK[/green] / [red]{fail} lỗi[/red]")

    console.rule()
    console.print(
        f"[bold]Tổng kết:[/bold] "
        f"[green]{total_ok} thành công[/green] / [red]{total_fail} thất bại[/red]"
    )


def main():
    cli()


if __name__ == "__main__":
    main()
