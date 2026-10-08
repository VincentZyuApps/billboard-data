# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "httpx",
# ]
# ///

import argparse
from datetime import datetime, timezone, date
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import httpx

UID = 12446725
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "niconico"
WEEKLY_DIR = DATA_DIR / "weekly"
INDEX_FILE = DATA_DIR / "index.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def get_client() -> httpx.Client:
    return httpx.Client(headers=HEADERS, timeout=15.0, follow_redirects=True)


def parse_issue_metadata(content: str, opus_id: str) -> Optional[Dict[str, Any]]:
    if "VOCALOID SONGS TOP20" not in content:
        return None

    date_match = re.search(r"【(\d{4})/(\d{2})/(\d{2})】", content)
    if not date_match:
        return None

    year = int(date_match.group(1))
    month = int(date_match.group(2))
    day = int(date_match.group(3))
    date_str = f"{year:04d}-{month:02d}-{day:02d}"

    base_date = date(2026, 10, 7)
    cur_date = date(year, month, day)
    diff_weeks = (cur_date - base_date).days // 7
    issue = 188 + diff_weeks

    filename = f"issue_{issue}_{date_str}.json"

    return {
        "issue": issue,
        "type": "weekly",
        "opus_id": str(opus_id),
        "title": content.strip(),
        "year": year,
        "date": date_str,
        "week": cur_date.isocalendar()[1],
        "source_url": f"https://www.bilibili.com/opus/{opus_id}",
        "path": f"weekly/{filename}",
    }


def fetch_opus_list(client: httpx.Client, max_pages: int = 100) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    offset = ""
    has_more = True
    page = 1

    print(f"[*] Starting to fetch Niconico opus list for UID {UID}...")

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
            if data.get("code") == 0 and data.get("data", {}).get("item"):
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

    current_rank = None
    current_song = ""
    current_author = ""
    current_prev_rank = ""
    current_weeks = None

    for p in paragraphs:
        ptype = p.get("para_type")
        if ptype == 1:
            text_nodes = p.get("text", {}).get("nodes", [])
            txt = "".join(n.get("word", {}).get("words", "") for n in text_nodes if n.get("word")).strip()

            rank_match = re.match(r"^第\s*(\d+)\s*位\s*(.*)$", txt)
            if rank_match:
                current_rank = int(rank_match.group(1))
                song_author = rank_match.group(2).strip()
                parts = song_author.split("/")
                current_song = parts[0].strip() if parts[0] else song_author
                current_author = parts[1].strip() if len(parts) > 1 else ""

            stat_match = re.search(r"上周[：:]\s*([0-9—\-]+).*?在榜周数[：:]\s*(\d+)", txt)
            if stat_match:
                current_prev_rank = stat_match.group(1).strip()
                current_weeks = int(stat_match.group(2))

        elif ptype == 6 and current_rank is not None:
            card = p.get("link_card", {}).get("card") or {}
            oid = str(card.get("oid") or "")
            results.append({
                "rank": current_rank,
                "title": current_song,
                "author": current_author,
                "prev_rank": current_prev_rank,
                "weeks": current_weeks,
                "aid": oid,
                "bvid": "",
                "url": f"https://www.bilibili.com/video/av{oid}" if oid else "",
                "pic_url": "",
            })
            current_rank = None

    results.sort(key=lambda x: x["rank"])
    return results, pub_time_str, pub_ts


def fetch_video_metadata_by_aid(client: httpx.Client, aid: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    if not aid:
        return None, None
    url = f"https://api.bilibili.com/x/web-interface/view?aid={aid}"
    try:
        resp = client.get(url, timeout=10.0)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0 and data.get("data"):
                d = data["data"]
                owner = d.get("owner") or {}
                stat = d.get("stat") or {}
                bvid = d.get("bvid", "")
                meta = {
                    "title": d.get("title", ""),
                    "pic": d.get("pic", ""),
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
                return bvid, meta
    except Exception as e:
        print(f"    [!] Error fetching video meta for aid {aid}: {e}")
    return None, None


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
    parser = argparse.ArgumentParser(description="Niconico Billboard Data Crawler")
    parser.add_argument("--all", action="store_true", help="Fetch all historical issues")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing issue files")
    parser.add_argument("--incremental", action="store_true", help="Incremental check (default)")
    args = parser.parse_args()

    max_pages = 100 if args.all else 2

    with get_client() as client:
        issue_list = fetch_opus_list(client, max_pages=max_pages)
        issue_list.sort(key=lambda x: x["issue"], reverse=True)

        if not issue_list:
            print("[*] No Niconico weekly issues found.")
            return

        latest_candidate = issue_list[0]["issue"]
        latest_date = issue_list[0]["date"]
        target_filename = f"issue_{latest_candidate}_{latest_date}.json"
        latest_file = WEEKLY_DIR / target_filename

        if not args.all and not args.force and latest_file.exists():
            print(f"[*] Incremental check: latest Niconico issue #{latest_candidate} ({target_filename}) already exists. Nothing to do!")
            return

        new_or_updated = 0

        for meta in issue_list:
            issue_num = meta["issue"]
            opus_id = meta["opus_id"]
            date_str = meta["date"]
            fname = f"issue_{issue_num}_{date_str}.json"
            target_file = WEEKLY_DIR / fname

            if target_file.exists() and not args.force:
                continue

            print(f"[*] Crawling Niconico issue {issue_num} (Opus ID: {opus_id}, Date: {date_str})...")
            try:
                items, pub_time_str, pub_ts = fetch_and_parse_detail(client, opus_id)

                for item in items:
                    aid = str(item.get("aid") or "")
                    if aid:
                        bvid, vmeta = fetch_video_metadata_by_aid(client, aid)
                        if bvid:
                            item["bvid"] = bvid
                            item["url"] = f"https://www.bilibili.com/video/{bvid}"
                        if vmeta:
                            item["video_meta"] = vmeta
                            if not item["pic_url"] and vmeta.get("pic"):
                                item["pic_url"] = vmeta["pic"]
                        time.sleep(0.15)

                detail_data = {
                    "source": "niconico",
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
                print(f"    Saved Niconico issue {issue_num} ({len(items)} songs, pub: {pub_time_str}) -> {target_file.name}")
                new_or_updated += 1
                time.sleep(0.5)
            except Exception as e:
                print(f"[!] Error fetching issue {issue_num}: {e}")

        # 重建 niconico/index.json
        all_local_weekly_files = list(WEEKLY_DIR.glob("issue_*.json"))
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
                        "path": f"weekly/{p.name}",
                    })
            except Exception as e:
                print(f"[!] Error reading {p}: {e}")

        final_index_issues.sort(key=lambda x: x["issue"], reverse=True)
        latest_issue = final_index_issues[0]["issue"] if final_index_issues else None

        index_data = {
            "source": "niconico",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "latest_issue": latest_issue,
            "total_issues": len(final_index_issues),
            "issues": final_index_issues,
        }

        save_json(INDEX_FILE, index_data)
        print(f"[*] Updated niconico/index.json! Latest: #{latest_issue}, Total: {len(final_index_issues)} issues. New/Updated: {new_or_updated}")


if __name__ == "__main__":
    main()
