# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "httpx",
# ]
# ///

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import httpx

UID = 3546800279522160
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
WEEKLY_DIR = DATA_DIR / "weekly"
INDEX_FILE = DATA_DIR / "index.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
}


def get_client() -> httpx.Client:
    return httpx.Client(headers=HEADERS, timeout=15.0, follow_redirects=True)


def parse_issue_metadata(content: str, opus_id: str) -> Optional[Dict[str, Any]]:
    # 匹配周榜期数
    issue_match = re.search(r"第\s*(\d+)\s*期", content)
    if not issue_match or "周榜" not in content:
        return None

    issue = int(issue_match.group(1))
    is_legend = "传说曲" in content
    ranking_type = "legend" if is_legend else "weekly"

    # 提取年份和日期
    date_str = ""
    year = None
    date_match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", content)
    if date_match:
        year = int(date_match.group(1))
        month = int(date_match.group(2))
        day = int(date_match.group(3))
        date_str = f"{year:04d}-{month:02d}-{day:02d}"

    # 提取周数
    week = None
    week_match = re.search(r"第\s*(\d+)\s*周", content)
    if week_match:
        week = int(week_match.group(1))

    return {
        "issue": issue,
        "type": ranking_type,
        "opus_id": str(opus_id),
        "title": content.strip(),
        "year": year,
        "date": date_str,
        "week": week,
        "source_url": f"https://www.bilibili.com/opus/{opus_id}",
        "path": f"weekly/{issue}.json" if ranking_type == "weekly" else f"legend/{issue}.json",
    }


def fetch_opus_list(client: httpx.Client, max_pages: int = 100) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    offset = ""
    has_more = True
    page = 1

    print(f"[*] Starting to fetch opus list for UID {UID}...")

    while has_more and page <= max_pages:
        url = f"https://api.bilibili.com/x/polymer/web-dynamic/v1/opus/feed/space?host_mid={UID}"
        if offset:
            url += f"&offset={offset}"

        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0 or not data.get("data"):
            print(f"[!] Warning: non-zero response: {data}")
            break

        feed_data = data["data"]
        raw_items = feed_data.get("items") or []

        for raw in raw_items:
            content = raw.get("content") or ""
            opus_id = raw.get("opus_id") or raw.get("id")
            meta = parse_issue_metadata(content, str(opus_id))
            if meta:
                items.append(meta)

        has_more = feed_data.get("has_more") is True
        offset = feed_data.get("offset") or ""
        print(f"    Page {page}: found {len(raw_items)} items, accumulated {len(items)} weekly items.")

        page += 1
        if has_more:
            time.sleep(0.5)

    return items


def fetch_and_parse_detail(client: httpx.Client, opus_id: str, retries: int = 3) -> Tuple[List[Dict[str, Any]], str, Optional[int]]:
    url = f"https://api.bilibili.com/x/polymer/web-dynamic/v1/opus/detail?id={opus_id}"
    data = None
    for attempt in range(1, retries + 1):
        try:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") == 0:
                if data.get("data", {}).get("fallback"):
                    print(f"        [*] Legacy cv article format, skipping.")
                    return [], "", None
                if data.get("data", {}).get("item"):
                    break
            print(f"        [!] Attempt {attempt} got response: {data.get('code')}, retrying...")
        except Exception as e:
            print(f"        [!] Attempt {attempt} error: {e}, retrying...")
        time.sleep(1.5 * attempt)

    if not data or data.get("code") != 0 or not data.get("data", {}).get("item"):
        raise ValueError(f"Failed to fetch opus detail for {opus_id}: {data}")

    item = data["data"]["item"]
    modules = item.get("modules") or []

    content_module = None
    pub_time_str = ""
    pub_ts = None

    for m in modules:
        m_type = m.get("module_type")
        if m_type == "MODULE_TYPE_CONTENT":
            content_module = m
        elif m_type == "MODULE_TYPE_AUTHOR":
            author = m.get("module_author") or {}
            pub_time_str = author.get("pub_time", "")
            pub_ts = author.get("pub_ts")

    if not content_module:
        return [], pub_time_str, pub_ts

    paragraphs = content_module.get("module_content", {}).get("paragraphs") or []
    results: List[Dict[str, Any]] = []
    current_entry: Optional[Dict[str, Any]] = None

    for p in paragraphs:
        text_obj = p.get("text")
        pic_obj = p.get("pic")

        if text_obj and text_obj.get("nodes"):
            nodes = text_obj["nodes"]
            full_text = "".join(
                node.get("word", {}).get("words", "") for node in nodes if node.get("word")
            )
            rank_match = re.search(r"第\s*(\d+)\s*名", full_text)
            if rank_match:
                rank = int(rank_match.group(1))

                # 寻找富文本链接节点
                rich_node = None
                for n in nodes:
                    if n.get("type") == "TEXT_NODE_TYPE_RICH" and n.get("rich"):
                        rich_node = n["rich"]
                        break

                song_title = ""
                bvid = ""
                jump_url = ""

                if rich_node:
                    song_title = rich_node.get("text", "").strip()
                    jump_url = rich_node.get("jump_url", "").strip()
                    bv_match = re.search(r"BV[0-9a-zA-Z]+", jump_url)
                    if bv_match:
                        bvid = bv_match.group(0)

                # Fallback: 如果没有 rich 节点，从纯文本中切分歌名
                if not song_title:
                    clean_text = re.sub(r"第\s*\d+\s*名\s*[-–—:]*\s*", "", full_text).strip()
                    song_title = clean_text

                current_entry = {
                    "rank": rank,
                    "title": song_title,
                    "bvid": bvid,
                    "url": jump_url,
                    "pic_url": "",
                }
                results.append(current_entry)

        elif pic_obj and current_entry and not current_entry["pic_url"]:
            pics = pic_obj.get("pics") or []
            if pics:
                current_entry["pic_url"] = pics[0].get("url", "")

    return results, pub_time_str, pub_ts


def fetch_video_metadata(client: httpx.Client, bvid: str) -> Optional[Dict[str, Any]]:
    if not bvid:
        return None
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    try:
        resp = client.get(url, timeout=10.0)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0 and data.get("data"):
                d = data["data"]
                owner = d.get("owner") or {}
                stat = d.get("stat") or {}
                return {
                    "title": d.get("title", ""),
                    "duration": d.get("duration", 0),
                    "pubdate": d.get("pubdate", 0),
                    "uploader": {
                        "mid": owner.get("mid", 0),
                        "name": owner.get("name", ""),
                        "face": owner.get("face", ""),
                    },
                    "stat": {
                        "view": stat.get("view", 0),
                        "danmaku": stat.get("danmaku", 0),
                        "reply": stat.get("reply", 0),
                        "favorite": stat.get("favorite", 0),
                        "coin": stat.get("coin", 0),
                        "share": stat.get("share", 0),
                        "like": stat.get("like", 0),
                    },
                }
    except Exception as e:
        print(f"    [!] Error fetching video meta for {bvid}: {e}")
    return None


def save_json(file_path: Path, data: Any) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(file_path: Path) -> Any:
    if not file_path.exists():
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Billboard Data Crawler")
    parser.add_argument("--all", action="store_true", help="Fetch all historical issues")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing issue files")
    parser.add_argument("--incremental", action="store_true", help="Incremental check (default)")
    args = parser.parse_args()

    max_pages = 100 if args.all else 2

    with get_client() as client:
        issue_list = fetch_opus_list(client, max_pages=max_pages)

        # 过滤周榜与排序
        weekly_issues = [it for it in issue_list if it["type"] == "weekly"]
        weekly_issues.sort(key=lambda x: x["issue"], reverse=True)

        if not weekly_issues:
            print("[*] No weekly issues found.")
            return

        # 检查是否增量模式下最新一期已存在
        latest_candidate = weekly_issues[0]["issue"]
        latest_file = WEEKLY_DIR / f"{latest_candidate}.json"
        if not args.all and not args.force and latest_file.exists():
            print(f"[*] Incremental check: latest issue #{latest_candidate} already exists. Nothing to do!")
            return

        new_or_updated = 0

        for meta in weekly_issues:
            issue_num = meta["issue"]
            opus_id = meta["opus_id"]
            target_file = WEEKLY_DIR / f"{issue_num}.json"

            if target_file.exists() and not args.force:
                continue

            print(f"[*] Crawling issue {issue_num} (Opus ID: {opus_id})...")
            try:
                items, pub_time_str, pub_ts = fetch_and_parse_detail(client, opus_id)

                # 补充每首歌曲的详细视频元数据
                for item in items:
                    bvid = item.get("bvid")
                    if bvid:
                        item["video_meta"] = fetch_video_metadata(client, bvid)
                        time.sleep(0.2)

                detail_data = {
                    "issue": issue_num,
                    "type": meta["type"],
                    "opus_id": opus_id,
                    "title": meta["title"],
                    "year": meta["year"],
                    "date": meta["date"],
                    "week": meta["week"],
                    "pub_time_str": pub_time_str,
                    "pub_ts": pub_ts,
                    "source_url": meta["source_url"],
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "total_ranked": len(items),
                    "items": items,
                }
                save_json(target_file, detail_data)
                print(f"    Saved issue {issue_num} ({len(items)} songs, pub: {pub_time_str}) -> {target_file.name}")
                new_or_updated += 1
                time.sleep(0.8)
            except Exception as e:
                print(f"[!] Error fetching issue {issue_num}: {e}")

        # 合并所有已存在的 weekly 详情并更新 index.json
        all_local_weekly_files = sorted(WEEKLY_DIR.glob("*.json"), key=lambda p: int(p.stem), reverse=True)
        final_index_issues = []

        for p in all_local_weekly_files:
            try:
                detail = load_json(p)
                if detail:
                    final_index_issues.append({
                        "issue": detail.get("issue"),
                        "type": detail.get("type", "weekly"),
                        "opus_id": detail.get("opus_id"),
                        "title": detail.get("title"),
                        "year": detail.get("year"),
                        "date": detail.get("date"),
                        "week": detail.get("week"),
                        "pub_time_str": detail.get("pub_time_str", ""),
                        "pub_ts": detail.get("pub_ts"),
                        "total_ranked": detail.get("total_ranked", len(detail.get("items", []))),
                        "source_url": detail.get("source_url"),
                        "path": f"weekly/{detail.get('issue')}.json",
                    })
            except Exception as e:
                print(f"[!] Error reading {p}: {e}")

        latest_issue = final_index_issues[0]["issue"] if final_index_issues else None

        index_data = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "latest_issue": latest_issue,
            "total_issues": len(final_index_issues),
            "issues": final_index_issues,
        }

        save_json(INDEX_FILE, index_data)
        print(f"[*] Updated index.json! Latest: #{latest_issue}, Total: {len(final_index_issues)} issues. New/Updated: {new_or_updated}")


if __name__ == "__main__":
    main()
