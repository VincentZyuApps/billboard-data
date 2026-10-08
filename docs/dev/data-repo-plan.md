# 数据仓库规划方案 (billboard-data)

> 目标：自动化抓取、结构化归档 Bilibili UP 主 **Bili Board Atel**（UID: `3546800279522160`）发布的《Bili Board 术力口周榜》专栏数据，并通过 CDN / GitHub 免费分发。

---

## 1. 仓库定位与职责

- **独立性**：纯数据仓库（Headless Data Repository），与下游具体的使用平台（如 Koishi 插件、网页端、其他机器人）解耦。
- **自动化**：利用 GitHub Actions 定时执行爬虫脚本，自动增量提交与推送。
- **免运维分发**：直接作为静态数据源，支持通过 `jsDelivr` / `GitHub Pages` 全球加速访问，零服务器成本。

---

## 2. 数据源与 API 调研

### 2.1 目标 UP 主信息
- **UID**: `3546800279522160`
- **专栏列表页**: `https://space.bilibili.com/3546800279522160/upload/opus`
- **内容特征**: 每周固定发布《Bili_Board术力口周榜第X期YYYY年MM月DD日第WW周》图文专栏。

### 2.2 核心接口验证
经过实测，B 站 Opus 接口公开可用且格式规范：

1. **专栏列表接口**
   - 请求 URL: `https://api.bilibili.com/x/polymer/web-dynamic/v1/opus/feed/space?host_mid=3546800279522160`
   - 翻页机制: 支持分页或游标 offset，用于初次爬取历史所有期数。
   - 关键返回: 每条包含 `opus_id`、`content`（标题/期数文本摘要）、`pub_time` 等。

2. **专栏详情接口**
   - 请求 URL: `https://api.bilibili.com/x/polymer/web-dynamic/v1/opus/detail?id={opus_id}`
   - 关键路径: `data.item.modules[module_type="MODULE_TYPE_CONTENT"].module_content.paragraphs`
   - 正文结构:
     - 排名与歌名段落: `paragraphs[i].text.nodes`
       - 文本节点: 如 `"第 1 名 - "`
       - 富文本链接节点: 类型为 `RICH_TEXT_NODE_TYPE_AV`，直接暴露 `text`（歌名）、`jump_url`、`bvid`、`rid`
     - 排名卡片图片段落: `paragraphs[i+1].pic.pics[0].url`（单曲数据海报大图）

---

## 3. 仓库目录与数据结构规范

### 3.1 目录组织

```text
billboard-data/
├── .github/
│   └── workflows/
│       └── crawl-weekly.yml      # GitHub Actions 定时任务工作流
├── scripts/
│   ├── crawler.ts (或 crawler.js) # 爬虫脚本 (支持全量与增量)
│   └── types.ts                  # TypeScript 类型定义
├── data/
│   ├── index.json                # 全局索引文件 (期数列表与元数据)
│   └── weekly/                   # 各期详细数据
│       ├── 120.json
│       ├── 121.json
│       └── 122.json
├── package.json
└── README.md
```

### 3.2 数据格式规范

#### (1) 全局索引 `data/index.json`
用于下游客户端快速获取期数列表、最新一期编号，而无需拉取所有大文件：

```json
{
  "updated_at": "2026-10-08T05:34:00Z",
  "latest_issue": 122,
  "total_issues": 122,
  "issues": [
    {
      "issue": 122,
      "opus_id": "1256401637754273800",
      "title": "Bili_Board术力口周榜第122期2026年10月7日第40周",
      "year": 2026,
      "week": 40,
      "pub_date": "2026-10-07",
      "path": "weekly/122.json"
    }
  ]
}
```

#### (2) 单期详情 `data/weekly/{issue}.json`
以第 122 期为例：

```json
{
  "issue": 122,
  "opus_id": "1256401637754273800",
  "title": "Bili_Board术力口周榜第122期2026年10月7日第40周",
  "pub_time": 1728288000,
  "source_url": "https://www.bilibili.com/opus/1256401637754273800",
  "items": [
    {
      "rank": 1,
      "title": "敌人",
      "bvid": "BV1UGa961Ejt",
      "jump_url": "https://www.bilibili.com/video/BV1UGa961Ejt",
      "pic_url": "http://i0.hdslb.com/bfs/new_dyn/812a518225581ae3f357c4c8ab9053f43546800279522160.jpg"
    }
  ]
}
```

---

## 4. 爬虫与自动化（GitHub Actions）设计

### 4.1 抓取策略
1. **历史全量抓取（初始化）**：
   - 运行一次 `npm run crawl:all`，带分页参数轮询专栏列表。
   - 解析历史所有周榜专栏并写入 `data/weekly/*.json`，生成初始 `data/index.json`。
2. **每周增量抓取（生产运行）**：
   - 运行 `npm run crawl:incremental`。
   - 仅拉取列表第 1 页。
   - 读取已有 `data/index.json`，若最新一期已存在则安全退出；若有新专栏，拉取详情并解析写入，更新 `index.json`。

### 4.2 GitHub Actions 工作流设计
- **触发条件**：
  - 定时调度：每周二、周三晚上北京时间 20:00、22:00（Cron: `0 12,14 * * 2,3`）。
  - 手动触发：`workflow_dispatch` 允许后台随时手动跑一次。
- **执行步骤**：
  1. `actions/checkout@v4` 拉取仓库代码与数据。
  2. 安装 Node.js 环境并安装极简依赖（`axios` 或原生 Node fetch）。
  3. 执行 `node scripts/crawler.js --incremental`。
  4. 检查 `git status -s`：
     - 若 `data/` 有更新，自动配置 bot 用户并 `git commit -m "chore(data): auto update weekly rankings"` 随后 `git push`。
     - 若无更新，静默结束。

---

## 5. 分发与 CDN 加速策略

下游客户端（如 Koishi 插件）无需克隆 Git 仓库，可直接通过以下方式访问静态 JSON：

- **jsDelivr CDN**（推荐，国内外解析快）：
  - 索引: `https://cdn.jsdelivr.net/gh/<owner>/billboard-data@main/data/index.json`
  - 单期: `https://cdn.jsdelivr.net/gh/<owner>/billboard-data@main/data/weekly/{issue}.json`
- **GitHub Raw**（备用源）：
  - `https://raw.githubusercontent.com/<owner>/billboard-data/main/data/index.json`
- **GitHub Pages**（可选开启）：
  - `https://<owner>.github.io/billboard-data/data/index.json`

---

## 6. 后续实施阶段与排期

1. **本地脚本实现与测试**：编写单脚本测试历史列表抓取与详情解析。
2. **全量数据归档**：在本地运行全量爬取，生成 `data/` 目录基础数据。
3. **编写 Actions 工作流**：配置 GitHub Actions 增量更新与自动 commit。
