# -*- coding: utf-8 -*-
"""
Tests for Headless-First CLI (cli.py).
Xác thực khả năng vận hành độc lập trực tiếp với SQLite khi Web Server không bật.
"""

import sys
import os
import shutil
import tempfile
import json
import subprocess
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

@pytest.fixture(scope="module", autouse=True)
def isolated_test_db():
    """Tạo bản sao tạm của SQLite DB để không làm bẩn data/prompts.db khi test."""
    orig_db = ROOT_DIR / "data" / "prompts.db"
    temp_dir = tempfile.mkdtemp()
    temp_db = Path(temp_dir) / "test_prompts.db"
    if orig_db.exists():
        shutil.copy2(str(orig_db), str(temp_db))
    os.environ["DB_PATH"] = str(temp_db)
    yield temp_db
    os.environ.pop("DB_PATH", None)
    shutil.rmtree(temp_dir, ignore_errors=True)


def run_cli(*args):
    """Chạy cli.py trong tiến trình con và thu thập stdout, stderr, returncode."""
    cmd = [sys.executable, str(ROOT_DIR / "cli.py")] + list(args)
    env = os.environ.copy()
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env
    )
    return proc


def test_cli_stats_json():
    """Kiểm tra lệnh stats --json xuất JSON sạch ra stdout."""
    res = run_cli("stats", "--json")
    assert res.returncode == 0, f"Error: {res.stderr}"
    data = json.loads(res.stdout)
    assert "total_prompts" in data
    assert data["total_prompts"] > 0
    assert "by_category" in data
    assert "image" in data["by_category"]


def test_cli_list_json():
    """Kiểm tra lệnh list --limit 3 --json xuất đúng 3 phần tử."""
    res = run_cli("list", "--limit", "3", "--json")
    assert res.returncode == 0, f"Error: {res.stderr}"
    data = json.loads(res.stdout)
    assert data["count"] == 3
    assert len(data["items"]) == 3
    first = data["items"][0]
    assert "id" in first
    assert "title" in first


def test_cli_list_filter_category():
    """Kiểm tra lọc theo danh mục video."""
    res = run_cli("list", "--category", "video", "--limit", "5", "--json")
    assert res.returncode == 0
    data = json.loads(res.stdout)
    for item in data["items"]:
        assert item["category"] == "video"


def test_cli_get_existing_prompt():
    """Kiểm tra lấy chi tiết một prompt đã tồn tại."""
    res = run_cli("get", "prompt_1", "--json")
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["id"] == "prompt_1"
    assert "title" in data
    assert "category" in data


def test_cli_get_raw():
    """Kiểm tra lấy nội dung prompt thô bằng cờ --raw."""
    res = run_cli("get", "prompt_1", "--raw")
    assert res.returncode == 0
    assert len(res.stdout.strip()) > 0


def test_cli_get_non_existent():
    """Kiểm tra trường hợp ID không tồn tại trả về exit code 1."""
    res = run_cli("get", "prompt_non_existent_999999", "--json")
    assert res.returncode == 1
    assert "Không tìm thấy prompt" in res.stderr
    assert res.stdout.strip() == ""


def test_cli_tags_list_json():
    """Kiểm tra liệt kê danh mục tags dạng JSON."""
    res = run_cli("tags", "list", "--json")
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert isinstance(data, list)
    assert len(data) > 0
    assert "tag" in data[0]
    assert "count" in data[0]


def test_cli_add_update_delete_lifecycle():
    """Kiểm tra vòng đời tạo mới, cập nhật và xóa prompt qua CLI."""
    # 1. Add
    test_title = "__TEST_CLI_PROMPT_LIFECYCLE__"
    res_add = run_cli(
        "add",
        "--content", "A temporary test prompt for automated testing",
        "--title", test_title,
        "--category", "content",
        "--note", "Temporary note",
        "--json"
    )
    assert res_add.returncode == 0, f"Add failed: {res_add.stderr}"
    data_add = json.loads(res_add.stdout)
    created_id = data_add["id"]
    assert created_id.startswith("prompt_")

    try:
        # 2. Update
        updated_title = "__TEST_CLI_PROMPT_UPDATED__"
        res_up = run_cli("update", created_id, "--title", updated_title, "--json")
        assert res_up.returncode == 0, f"Update failed: {res_up.stderr}"
        data_up = json.loads(res_up.stdout)
        assert data_up["prompt"]["title"] == updated_title

        # 3. Verify with get
        res_get = run_cli("get", created_id, "--json")
        assert res_get.returncode == 0
        data_get = json.loads(res_get.stdout)
        assert data_get["title"] == updated_title

    finally:
        # 4. Delete
        res_del = run_cli("delete", created_id, "--force", "--json")
        assert res_del.returncode == 0, f"Delete failed: {res_del.stderr}"
        data_del = json.loads(res_del.stdout)
        assert data_del["deleted"] is True

        # Verify it's gone
        res_check = run_cli("get", created_id, "--json")
        assert res_check.returncode == 1
