# billboard-data

📊 Bili & Nico 术力口双周榜公开专栏数据归档 🎵 GitHub Actions 自动巡检 ⚡ 开放静态数据源与 CDN API 接口 ✨

收录以下公开周榜专栏的结构化数据源：
1. **Bili Board 本地周榜**：Bilibili UP 主 **Bili-Board_Atel**（UID: [3546800279522160](https://space.bilibili.com/3546800279522160/upload/opus)）每周三晚发布的《Bili Board 术力口周榜》。
2. **Niconico 日本周榜**：Bilibili UP 主 **Elvansphere**（UID: [12446725](https://space.bilibili.com/12446725/upload/opus)）每周三发布的《ニコニコ VOCALOID SONGS TOP20》搬运与评析专栏。

---

## 📅 更新频率与 GitHub Actions 调度

- **Bili Board 周榜**：通常于 **每周三晚上 18:00** 准时发布。GitHub Actions 于 **每周三 18:05**（及 18:35 兜底）自动检测并归档新数据。
- **Niconico 周榜**：通常于 **每周三傍晚至晚间（19:00~20:30）** 不定时发布。GitHub Actions 于 **每周三 19:00 ~ 20:30** 每隔 10 分钟自动轮询巡检并归档新数据。

---

## 🌐 免费公共 CDN 调用方式

任何前端网页、小程序、桌面应用、机器人应用（如 Koishi 插件、NoneBot 插件、AstrBot 插件等），均可直接免鉴权调用本仓库数据：

### 1. 全局索引文件（推荐首选拉取）
包含对应数据源已收录的期数列表、最新一期编号及更新时间：
- **Bili Board 索引**：
  ```text
  https://cdn.jsdelivr.net/gh/VincentZyu233/billboard-data@main/data/bilibili/index.json
  ```
- **Niconico 索引**：
  ```text
  https://cdn.jsdelivr.net/gh/VincentZyu233/billboard-data@main/data/niconico/index.json
  ```

### 2. 单期详细数据文件
获取指定期号的详细排名清单（TOP 20）：
- **Bili Board 单期数据**（示例：第 122 期）：
  ```text
  https://cdn.jsdelivr.net/gh/VincentZyu233/billboard-data@main/data/bilibili/weekly/issue_122_2026-10-07.json
  ```
- **Niconico 单期数据**（示例：第 188 期）：
  ```text
  https://cdn.jsdelivr.net/gh/VincentZyu233/billboard-data@main/data/niconico/weekly/issue_188_2026-10-07.json
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
# B站周榜爬虫（增量 / 全量 / 强制刷新）
uv run scripts/crawler_bilibili.py --incremental
uv run scripts/crawler_bilibili.py --all
uv run scripts/crawler_bilibili.py --all --force

# N站周榜爬虫（增量 / 全量 / 强制刷新）
uv run scripts/crawler_niconico.py --incremental
uv run scripts/crawler_niconico.py --all
uv run scripts/crawler_niconico.py --all --force
```
