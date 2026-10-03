#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Prompt Studio - Headless-First CLI
Lệnh điều khiển độc lập trực tiếp từ terminal, không cần bật Web Server.
"""

import sys
import os
import json
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any

# Cấu hình UTF-8 chống lỗi cp1252 trên Windows PowerShell / CMD
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Thêm thư mục gốc vào sys.path để import app modules
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.database import ensure_database
from app.db.repository import PromptRepository
from app.services.parser import parse_incoming_prompt


def log_err(msg: str):
    """Ghi thông báo lỗi hoặc tiến trình ra stderr để bảo vệ stdout sạch cho JSON."""
    print(f"[!] {msg}", file=sys.stderr)


def log_info(msg: str):
    """Ghi thông tin phụ trợ ra stderr."""
    print(f"[*] {msg}", file=sys.stderr)


def cmd_list(args):
    """Liệt kê danh sách prompts với các bộ lọc và hỗ trợ xuất JSON sạch."""
    cat = args.category
    if cat == "all":
        cat = None
    elif cat == "character":
        cat = "image"

    limit = args.limit if args.limit and args.limit > 0 else None
    offset = args.offset if args.offset and args.offset >= 0 else 0

    prompts = PromptRepository.get_prompts(
        query=args.query,
        tag=args.tag or "all",
        category=cat,
        limit=limit,
        offset=offset
    )

    if args.json:
        payload = {
            "count": len(prompts),
            "category": args.category,
            "tag": args.tag or "all",
            "query": args.query,
            "limit": limit,
            "offset": offset,
            "items": prompts
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if not prompts:
        print("Không tìm thấy prompt nào phù hợp tiêu chí.")
        return 0

    print(f"{'ID':<16} | {'LOẠI':<8} | {'ẢNH':<5} | {'TIÊU ĐỀ'}")
    print("-" * 75)
    for p in prompts:
        p_id = str(p.get("id", ""))
        p_cat = str(p.get("category", "image"))
        img_count = p.get("image_count", 0)
        title = (p.get("title") or "Không tiêu đề").strip()
        if len(title) > 42:
            title = title[:39] + "..."
        print(f"{p_id:<16} | {p_cat:<8} | {img_count:<5} | {title}")

    print("-" * 75)
    print(f"Tổng cộng: {len(prompts)} prompt(s)")
    return 0


def cmd_get(args):
    """Lấy chi tiết 1 prompt theo ID."""
    prompt = PromptRepository.get_prompt_by_id(args.prompt_id)
    if not prompt:
        log_err(f"Không tìm thấy prompt với ID '{args.prompt_id}'.")
        return 1

    if args.raw:
        # Xuất thuần nội dung prompt code / raw_content
        content = prompt.get("prompt_code") or prompt.get("raw_content") or ""
        print(content)
        return 0

    if args.json:
        print(json.dumps(prompt, ensure_ascii=False, indent=2))
        return 0

    print("=" * 60)
    print(f"ID       : {prompt.get('id')}")
    print(f"Tiêu đề  : {prompt.get('title')}")
    print(f"Danh mục : {prompt.get('category')}")
    print(f"Loại     : {prompt.get('prompt_type')}")
    print(f"Cần ref  : {'Có' if prompt.get('requires_reference') else 'Không'}")
    if prompt.get("note"):
        print(f"Ghi chú  : {prompt.get('note')}")

    tags = prompt.get("tags", [])
    if tags:
        print(f"Tags     : {', '.join(tags)}")

    images = prompt.get("images", [])
    if images:
        print(f"Ảnh ({len(images)}):")
        for img in images:
            status = img.get("status", "")
            fname = img.get("filename") or img.get("url")
            print(f"  - [{status}] {fname}")

    print("\n--- NỘI DUNG PROMPT ---")
    content = prompt.get("prompt_code") or prompt.get("raw_content") or ""
    print(content)

    compact = prompt.get("compact_prompt")
    if compact:
        print("\n--- PROMPT RÚT GỌN ---")
        print(compact)

    print("=" * 60)
    return 0


def cmd_add(args):
    """Thêm prompt mới từ chuỗi tham số, file hoặc stdin."""
    raw_content = ""
    if args.content:
        raw_content = args.content
    elif args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            log_err(f"Tệp không tồn tại: {args.file}")
            return 1
        raw_content = file_path.read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        raw_content = sys.stdin.read()

    raw_content = raw_content.strip()
    if not raw_content:
        log_err("Nội dung prompt không được để trống. Sử dụng --content, --file hoặc pipe từ stdin.")
        return 1

    parsed_data = parse_incoming_prompt(raw_content=raw_content, raw_media=None)

    media_list = []
    if args.media:
        import re
        lines = re.split(r'[\r\n,]+', args.media.strip())
        for l in lines:
            cleaned = l.strip()
            if cleaned:
                media_list.append(cleaned)

    if media_list:
        parsed_data["images"] = media_list

    category = args.category or "image"
    if category == "character":
        category = "image"
    parsed_data["category"] = category

    if args.title:
        parsed_data["title"] = args.title
    if args.note:
        parsed_data["note"] = args.note
    if args.requires_reference is not None:
        parsed_data["requires_reference"] = args.requires_reference

    try:
        new_prompt = PromptRepository.create_prompt(parsed_data=parsed_data)
        msg = "Tạo prompt thành công"

        if not new_prompt:
            log_err("Không thể tạo prompt.")
            return 1

        if args.json:
            print(json.dumps({
                "status": "success",
                "id": new_prompt["id"],
                "title": new_prompt["title"],
                "category": new_prompt["category"],
                "message": msg
            }, ensure_ascii=False, indent=2))
        else:
            log_info("Đã tạo prompt thành công!")
            print(f"ID: {new_prompt['id']}")
            print(f"Tiêu đề: {new_prompt['title']}")
        return 0
    except Exception as e:
        log_err(f"Lỗi khi lưu prompt: {e}")
        return 1


def cmd_update(args):
    """Cập nhật thông tin tiêu đề, ghi chú hoặc danh mục của prompt."""
    prompt = PromptRepository.get_prompt_by_id(args.prompt_id)
    if not prompt:
        log_err(f"Không tìm thấy prompt với ID '{args.prompt_id}'.")
        return 1

    updated = False
    if args.title is not None:
        PromptRepository.update_prompt_title(args.prompt_id, args.title)
        updated = True

    if args.note is not None:
        PromptRepository.update_prompt_note(args.prompt_id, args.note)
        updated = True

    if args.category is not None:
        if not PromptRepository.update_prompt_category(args.prompt_id, args.category):
            log_err(f"Danh mục không hợp lệ: {args.category}. Chấp nhận: image, video, content.")
            return 1
        updated = True

    if args.requires_reference is not None:
        PromptRepository.update_prompt_requires_reference(args.prompt_id, args.requires_reference)
        updated = True

    if args.compact is not None:
        PromptRepository.update_compact_prompt(args.prompt_id, args.compact)
        updated = True

    if not updated:
        log_info("Không có trường nào được chỉ định để cập nhật.")

    refreshed = PromptRepository.get_prompt_by_id(args.prompt_id)
    if args.json:
        print(json.dumps({"status": "success", "prompt": refreshed}, ensure_ascii=False, indent=2))
    else:
        log_info(f"Đã cập nhật prompt {args.prompt_id} thành công.")
    return 0


def cmd_delete(args):
    """Xóa prompt theo ID."""
    prompt = PromptRepository.get_prompt_by_id(args.prompt_id)
    if not prompt:
        log_err(f"Không tìm thấy prompt với ID '{args.prompt_id}'.")
        return 1

    if not args.force:
        confirm = input(f"Bạn có chắc muốn xóa prompt '{prompt.get('title')}' ({args.prompt_id})? [y/N]: ")
        if confirm.strip().lower() not in ("y", "yes"):
            log_info("Đã hủy thao tác xóa.")
            return 0

    success = PromptRepository.delete_prompt(args.prompt_id)
    if success:
        if args.json:
            print(json.dumps({"status": "success", "id": args.prompt_id, "deleted": True}, ensure_ascii=False))
        else:
            log_info(f"Đã xóa prompt '{args.prompt_id}' thành công.")
        return 0
    else:
        log_err(f"Xóa prompt '{args.prompt_id}' thất bại.")
        return 1


def cmd_tags(args):
    """Quản lý các thẻ tag của prompts."""
    subaction = args.tag_action

    if subaction == "list" or not subaction:
        tags = PromptRepository.get_tags(limit=100)
        if args.json:
            print(json.dumps(tags, ensure_ascii=False, indent=2))
        else:
            if not tags:
                print("Chưa có thẻ tag nào trong hệ thống.")
                return 0
            print(f"{'TAG':<25} | {'SỐ LƯỢNG'}")
            print("-" * 37)
            for t in tags:
                print(f"{t['tag']:<25} | {t['count']}")
        return 0

    if subaction == "show":
        if not args.prompt_id:
            log_err("Cần cung cấp <prompt_id> để xem tags.")
            return 1
        tags = PromptRepository.get_prompt_tags(args.prompt_id)
        if args.json:
            print(json.dumps({"prompt_id": args.prompt_id, "tags": tags}, ensure_ascii=False, indent=2))
        else:
            print(f"Tags của {args.prompt_id}: {', '.join(tags) if tags else '(chưa có)'}")
        return 0

    if subaction == "add":
        if not args.prompt_id or not args.tag_name:
            log_err("Cần cung cấp <prompt_id> và <tag_name>.")
            return 1
        PromptRepository.add_tag_to_prompt(args.prompt_id, args.tag_name)
        tags = PromptRepository.get_tags_for_prompt(args.prompt_id)
        if args.json:
            print(json.dumps({"status": "success", "prompt_id": args.prompt_id, "tags": tags}, ensure_ascii=False))
        else:
            log_info(f"Đã thêm tag '{args.tag_name}' vào prompt '{args.prompt_id}'.")
        return 0

    if subaction == "remove" or subaction == "del":
        if not args.prompt_id or not args.tag_name:
            log_err("Cần cung cấp <prompt_id> và <tag_name>.")
            return 1
        PromptRepository.remove_tag_from_prompt(args.prompt_id, args.tag_name)
        tags = PromptRepository.get_tags_for_prompt(args.prompt_id)
        if args.json:
            print(json.dumps({"status": "success", "prompt_id": args.prompt_id, "tags": tags}, ensure_ascii=False))
        else:
            log_info(f"Đã xóa tag '{args.tag_name}' khỏi prompt '{args.prompt_id}'.")
        return 0

    log_err(f"Hành động tag không hợp lệ: {subaction}")
    return 1


def cmd_stats(args):
    """Xem thống kê tổng quan cơ sở dữ liệu prompts."""
    stats = PromptRepository.get_stats()
    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return 0

    print("==================================================")
    print("        THỐNG KÊ AI PROMPT STUDIO DATABASE")
    print("==================================================")
    print(f"Tổng số Prompt       : {stats.get('total_prompts', 0)}")
    print(f"Tổng số Ảnh          : {stats.get('total_images', 0)}")
    print(f" - Đã tải xuống     : {stats.get('downloaded_images', 0)}")
    print(f" - Đang chờ tải     : {stats.get('pending_images', 0)}")
    print(f" - Tải thất bại     : {stats.get('failed_images', 0)}")
    print("-" * 50)
    print("Phân bố theo danh mục:")
    for cat, count in stats.get("by_category", {}).items():
        print(f" - {cat:<12}: {count}")
    print("--------------------------------------------------")
    print("Phân bố theo loại:")
    for p_type, count in stats.get("by_type", {}).items():
        print(f" - {p_type:<12}: {count}")
    print("==================================================")
    return 0


def cmd_export(args):
    """Xuất danh sách prompt ra file JSON hoặc stdout."""
    cat = args.category
    if cat == "all":
        cat = None
    prompts = PromptRepository.get_prompts(tag=args.tag or "all", category=cat, limit=None)

    full_items = []
    for p in prompts:
        full_p = PromptRepository.get_prompt_by_id(p["id"])
        if full_p:
            full_items.append(full_p)

    out_data = {
        "version": "1.1.0",
        "exported_count": len(full_items),
        "items": full_items
    }

    if args.output:
        out_path = Path(args.output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")
        log_info(f"Đã xuất {len(full_items)} prompts ra tệp: {out_path}")
    else:
        print(json.dumps(out_data, ensure_ascii=False, indent=2))
    return 0


def cmd_serve(args):
    """Khởi động Web Server (Uvicorn)."""
    import uvicorn
    import webbrowser
    import threading
    import time
    from app.config import HOST, DB_PATH, find_free_port

    active_port = args.port if args.port else find_free_port()
    browser_host = "127.0.0.1" if args.host in ("0.0.0.0", "") else args.host
    url = f"http://{browser_host}:{active_port}"

    log_info("==================================================")
    log_info("       AI PROMPT STUDIO - WEB SERVER")
    log_info("==================================================")
    log_info(f" - Cơ sở dữ liệu : {DB_PATH}")
    log_info(f" - Địa chỉ Web   : {url}")
    log_info(f" - Tài liệu API  : {url}/docs/api")
    log_info("--------------------------------------------------")

    if not args.no_browser:
        def _open():
            time.sleep(1.2)
            log_info(f"Đang mở trình duyệt tại {url} ...")
            webbrowser.open(url)
        threading.Thread(target=_open, daemon=True).start()

    log_info(f"Khởi động máy chủ tại {url} (Nhấn Ctrl+C để dừng)...")
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=active_port,
        reload=args.reload,
        log_level="info"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aff-prompt",
        description="AI Prompt Studio - CLI Headless & Server Management Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ sử dụng:
  aff-prompt list --category image --limit 10
  aff-prompt list --tag portrait --json
  aff-prompt get prompt_12 --json
  aff-prompt get prompt_12 --raw
  aff-prompt add --content "A photorealistic portrait of Vietnamese girl..." --title "Vietnamese KOC"
  aff-prompt stats --json
  aff-prompt tags list
  aff-prompt serve --port 8000 --no-browser
        """
    )
    parser.add_argument("-v", "--version", action="version", version="%(prog)s 1.1.0")

    subparsers = parser.add_subparsers(dest="subcommand", help="Lệnh chức năng")

    # Command: list
    p_list = subparsers.add_parser("list", help="Liệt kê danh sách prompts")
    p_list.add_argument("-q", "--query", type=str, help="Từ khóa tìm kiếm (tiêu đề, nội dung, note)")
    p_list.add_argument("-t", "--tag", type=str, default="all", help="Lọc theo tag (all, has_img, portrait, video, ...)")
    p_list.add_argument("-c", "--category", type=str, default="all", choices=["all", "image", "video", "content"], help="Lọc theo danh mục")
    p_list.add_argument("-l", "--limit", type=int, default=20, help="Số lượng kết quả (mặc định: 20)")
    p_list.add_argument("--offset", type=int, default=0, help="Vị trí bắt đầu (offset)")
    p_list.add_argument("--json", action="store_true", help="Xuất kết quả định dạng JSON sạch ra stdout")
    p_list.set_defaults(func=cmd_list)

    # Command: get
    p_get = subparsers.add_parser("get", help="Xem chi tiết một prompt")
    p_get.add_argument("prompt_id", type=str, help="ID của prompt cần xem (ví dụ: prompt_1)")
    p_get.add_argument("--json", action="store_true", help="Xuất chi tiết định dạng JSON sạch ra stdout")
    p_get.add_argument("--raw", action="store_true", help="Chỉ xuất nội dung prompt thuần (raw content/code)")
    p_get.set_defaults(func=cmd_get)

    # Command: add
    p_add = subparsers.add_parser("add", help="Thêm prompt mới vào cơ sở dữ liệu")
    p_add.add_argument("--content", type=str, help="Nội dung câu lệnh prompt (text hoặc JSON)")
    p_add.add_argument("-f", "--file", type=str, help="Đường dẫn tệp chứa nội dung câu lệnh")
    p_add.add_argument("-t", "--title", type=str, help="Tiêu đề tùy chỉnh")
    p_add.add_argument("-c", "--category", type=str, default="image", choices=["image", "video", "content"], help="Danh mục (mặc định: image)")
    p_add.add_argument("-n", "--note", type=str, default="", help="Ghi chú thêm cho prompt")
    p_add.add_argument("-m", "--media", type=str, help="URL hoặc đường dẫn ảnh/video mẫu đính kèm")
    p_add.add_argument("--requires-reference", action="store_true", default=None, help="Đánh dấu cần ảnh tham chiếu")
    p_add.add_argument("--json", action="store_true", help="Xuất kết quả tạo mới định dạng JSON ra stdout")
    p_add.set_defaults(func=cmd_add)

    # Command: update
    p_update = subparsers.add_parser("update", help="Cập nhật thông tin một prompt")
    p_update.add_argument("prompt_id", type=str, help="ID của prompt cần cập nhật")
    p_update.add_argument("-t", "--title", type=str, help="Tiêu đề mới")
    p_update.add_argument("-n", "--note", type=str, help="Ghi chú mới")
    p_update.add_argument("-c", "--category", type=str, choices=["image", "video", "content"], help="Danh mục mới")
    p_update.add_argument("--requires-reference", type=lambda x: (str(x).lower() in ['true','1', 'yes']), help="Đổi cờ cần ảnh tham chiếu (true/false)")
    p_update.add_argument("--compact", type=str, help="Cập nhật câu lệnh prompt rút gọn")
    p_update.add_argument("--json", action="store_true", help="Xuất kết quả định dạng JSON ra stdout")
    p_update.set_defaults(func=cmd_update)

    # Command: delete
    p_del = subparsers.add_parser("delete", help="Xóa prompt khỏi cơ sở dữ liệu")
    p_del.add_argument("prompt_id", type=str, help="ID của prompt cần xóa")
    p_del.add_argument("-y", "--force", action="store_true", help="Xác nhận xóa bỏ qua câu hỏi xác thực")
    p_del.add_argument("--json", action="store_true", help="Xuất kết quả định dạng JSON ra stdout")
    p_del.set_defaults(func=cmd_delete)

    # Command: tags
    p_tags = subparsers.add_parser("tags", help="Quản lý thẻ tags")
    p_tags.add_argument("tag_action", nargs="?", default="list", choices=["list", "show", "add", "remove", "del"], help="Hành động: list, show, add, remove")
    p_tags.add_argument("prompt_id", nargs="?", type=str, help="ID của prompt (khi dùng show, add, remove)")
    p_tags.add_argument("tag_name", nargs="?", type=str, help="Tên thẻ tag (khi dùng add, remove)")
    p_tags.add_argument("--json", action="store_true", help="Xuất kết quả định dạng JSON ra stdout")
    p_tags.set_defaults(func=cmd_tags)

    # Command: stats
    p_stats = subparsers.add_parser("stats", help="Xem số liệu thống kê cơ sở dữ liệu")
    p_stats.add_argument("--json", action="store_true", help="Xuất thống kê định dạng JSON ra stdout")
    p_stats.set_defaults(func=cmd_stats)

    # Command: export
    p_export = subparsers.add_parser("export", help="Xuất dữ liệu prompts ra file JSON")
    p_export.add_argument("-o", "--output", type=str, help="Đường dẫn file JSON xuất ra (mặc định: xuất ra stdout)")
    p_export.add_argument("-c", "--category", type=str, choices=["all", "image", "video", "content"], help="Lọc theo danh mục")
    p_export.add_argument("-t", "--tag", type=str, default="all", help="Lọc theo tag")
    p_export.set_defaults(func=cmd_export)

    # Command: serve
    from app.config import HOST
    p_serve = subparsers.add_parser("serve", help="Khởi động máy chủ Web UI & API")
    p_serve.add_argument("--host", type=str, default=HOST, help=f"Host (mặc định: {HOST})")
    p_serve.add_argument("--port", type=int, default=0, help="Port (mặc định: ngẫu nhiên)")
    p_serve.add_argument("--reload", action="store_true", default=True, help="Bật chế độ Auto-reload")
    p_serve.add_argument("--no-reload", dest="reload", action="store_false", help="Tắt chế độ Auto-reload")
    p_serve.add_argument("--no-browser", action="store_true", help="Không tự động mở trình duyệt")
    p_serve.set_defaults(func=cmd_serve)

    return parser


def main():
    ensure_database()
    parser = build_parser()
    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(0)

    try:
        code = args.func(args)
        sys.exit(code if isinstance(code, int) else 0)
    except KeyboardInterrupt:
        log_info("\nĐã hủy tác vụ bởi người dùng.")
        sys.exit(0)
    except Exception as e:
        log_err(f"Lỗi thực thi: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
