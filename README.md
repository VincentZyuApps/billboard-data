# billboard-data

《Bili Board 术力口周榜》（VOCALOID / 虚拟歌手周榜）公开结构化数据源。

数据来源：Bilibili UP 主 **Bili Board Atel**（UID: [3546800279522160](https://space.bilibili.com/3546800279522160/upload/opus)）每周发布的周榜专栏。

---

## 📅 更新频率与调度

- 周榜通常于 **每周三晚上 18:00** 准时发布。
- 本仓库通过 GitHub Actions 于 **每周三 18:05**（及 18:35 兜底）自动运行增量爬虫检测并归档新数据。

---

## 🌐 免费公共 CDN 调用方式

任何前端网页、小程序、桌面应用、机器人应用 （如 koishi插件、 nonebot插件、astrbot插件等） 等，均可直接免鉴权调用本仓库数据：

### 1. 全局索引文件（推荐首选拉取）
包含所有已收录的期数列表、最新一期编号及更新时间：
```text
https://cdn.jsdelivr.net/gh/VincentZyu233/billboard-data@main/data/index.json
```

### 2. 单期详细数据文件
获取指定期号（如第 122 期）的排名清单（1 ~ 20 名）：
```text
https://cdn.jsdelivr.net/gh/VincentZyu233/billboard-data@main/data/weekly/122.json
```

---

## 📊 数据结构格式

### `data/index.json`
```json
{
  "updated_at": "2026-10-08T05:42:00Z",
  "latest_issue": 122,
  "total_issues": 70,
  "issues": [
    {
      "issue": 122,
      "type": "weekly",
      "opus_id": "1256401637754273800",
      "title": "Bili_Board术力口周榜第122期2026年10月7日第40周",
      "year": 2026,
      "date": "2026-10-07",
      "week": 40,
      "pub_time_str": "2026年10月07日 18:00",
      "pub_ts": 1791367202,
      "total_ranked": 20,
      "source_url": "https://www.bilibili.com/opus/1256401637754273800",
      "path": "weekly/122.json"
    }
  ]
}
```

### `data/weekly/{issue}.json`
```json
{
  "issue": 122,
  "type": "weekly",
  "opus_id": "1256401637754273800",
  "title": "Bili_Board术力口周榜第122期2026年10月7日第40周",
  "year": 2026,
  "date": "2026-10-07",
  "week": 40,
  "pub_time_str": "2026年10月07日 18:00",
  "pub_ts": 1791367202,
  "source_url": "https://www.bilibili.com/opus/1256401637754273800",
  "updated_at": "2026-10-08T05:42:00Z",
  "total_ranked": 20,
  "items": [
    {
      "rank": 1,
      "title": "敌人",
      "bvid": "BV1UGa961Ejt",
      "url": "https://www.bilibili.com/video/BV1UGa961Ejt",
      "pic_url": "http://i0.hdslb.com/bfs/new_dyn/812a518225581ae3f357c4c8ab9053f43546800279522160.jpg"
    }
  ]
}
```

---

## 🛠 本地运行

使用现代 Python 包管理器 `uv`：

```bash
# 增量检查并更新
uv run scripts/crawler.py --incremental

# 全量回溯历史期数
uv run scripts/crawler.py --all

# 强制覆盖刷新本地所有已存期数
uv run scripts/crawler.py --all --force
```
