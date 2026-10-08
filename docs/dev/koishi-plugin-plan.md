# Koishi 插件规划方案 (koishi-plugin-biliboard)

> 目标：打造一款用于查询《Bili Board 术力口周榜》（VOCALOID/虚拟歌手周榜）的 Koishi 插件，支持最新周榜展示、历史期数回溯、曲目历史排行检索与新榜发布订阅提醒。

---

## 1. 插件定位与特性

- **轻量即用**：无需本地部署数据库，直接读取静态数据源（`billboard-data` CDN），极速启动。
- **两级缓存**：内存缓存（LRU Cache）+ 本地持久化缓存，请求网络最小化，响应毫秒级。
- **多端展示**：
  - 默认模式：整洁清晰的结构化文本排版（适配各平台文字聊天）。
  - 可选模式：通过 `puppeteer` 或 `canvas` 渲染精美排行榜卡片图片（视觉体验更佳）。
- **可订阅推送**：群聊可设置每周自动推送最新周榜，省去人工搬运。

---

## 2. 插件架构设计

```text
koishi-plugin-biliboard/
├── src/
│   ├── index.ts              # 插件入口，注册服务与指令
│   ├── config.ts             # 插件配置 Schema
│   ├── service.ts            # 数据拉取、更新调度与缓存管理
│   ├── commands/
│   │   ├── latest.ts         # 最新周榜指令
│   │   ├── query.ts          # 历史期数查询指令
│   │   ├── search.ts         # 查歌指令
│   │   └── subscribe.ts      # 订阅推送管理
│   ├── render/
│   │   ├── text.ts           # 文本排版渲染器
│   │   └── image.ts          # 图片卡片渲染器 (可选服务)
│   └── types.ts              # 数据结构与类型定义
├── package.json
├── tsconfig.json
└── README.md
```

### 核心分层：
1. **数据与网络层 (`service.ts`)**：
   - 维护一个内存索引列表（由 `index.json` 解析而来）。
   - 提供 `getLatestRanking()`、`getRankingByIssue(issue)`、`searchSong(keyword)`。
   - 实现自动重试与 CDN 降级（jsDelivr -> GitHub Raw -> 自定义源）。
2. **缓存层**：
   - 周榜数据具有“发布后历史数据不可变”的特性。
   - 已拉取的历史期数（如 `120.json`）永久在本地缓存，绝不重复发送 HTTP 请求。
   - `index.json` 设置 10~30 分钟缓存或随定时任务更新。
3. **指令交互层 (`commands/`)**：
   - 定义 Koishi 友好的中英文别名、选项提示、帮助文档。
4. **渲染层 (`render/`)**：
   - 根据群聊设置或用户传入的 `--image` 选项选择纯文本或渲染图片。

---

## 3. 指令系统设计

### 3.1 核心命令树

| 指令 | 别名 | 描述 | 示例 |
| :--- | :--- | :--- | :--- |
| `周榜` | `术力口周榜`, `bb.latest` | 查看最新一期的周榜排行 | `周榜`、`周榜 -n 10` |
| `周榜.历史 <期数>` | `周榜 <期数>`, `bb.issue` | 查询指定期数的周榜排行 | `周榜 120`、`周榜.历史 118` |
| `周榜.搜歌 <关键词>` | `周榜 查歌 <关键词>` | 搜索某首歌曲在周榜中出现的历史排位记录 | `周榜 搜歌 敌人` |
| `周榜.订阅` | `bb.sub` | 在当前群开启或关闭新榜自动提醒 | `周榜.订阅 on`、`周榜.订阅 off` |
| `周榜.更新` | `bb.reload` | 管理员强制刷新远程索引 | `周榜.更新` |

### 3.2 交互输出预览示例

#### 文本模式（默认）
```text
🎵【Bili Board 术力口周榜】第 122 期（2026年第40周）
━━━━━━━━━━━━━━━
🥇 第 1 名：敌人
   ▶ 链接：https://bilibili.com/video/BV1UGa961Ejt
🥈 第 2 名：[歌名]
   ▶ 链接：https://bilibili.com/video/[BV号]
🥉 第 3 名：[歌名]
   ▶ 链接：https://bilibili.com/video/[BV号]
4. [歌名] (BVxxxx)
5. [歌名] (BVxxxx)
...
━━━━━━━━━━━━━━━
💡 提示：使用「周榜 121」查看上一期，「周榜 查歌 <歌名>」检索历史战绩。
```

---

## 4. 插件配置项（Config Schema）

```typescript
export interface Config {
  // 数据源配置
  dataSourceUrl: string;       // 默认: 'https://cdn.jsdelivr.net/gh/<owner>/billboard-data@main/data'
  fallbackSourceUrl?: string;   // 备用源: 'https://raw.githubusercontent.com/<owner>/billboard-data/main/data'
  
  // 显示偏好
  defaultTopCount: number;     // 默认展示前多少名，默认: 10（支持参数 -n 扩充至 20 或全部）
  renderMode: 'text' | 'image' | 'auto'; // 渲染模式：纯文本 / 卡片图 / 自动
  
  // 定时与更新
  indexSyncInterval: number;   // 索引同步周期（分钟），默认 30 分钟
  enableAutoBroadcast: boolean;// 是否启用新榜自动广播
  broadcastChannels: string[]; // 订阅的群组频道列表
}
```

---

## 5. 依赖与集成考量

1. **基础依赖**：
   - `koishi`: 核心框架支持
   - 可选 `canvas` 或 `koishi-plugin-puppeteer`: 用于排行榜长图渲染（若开启图片模式）。
2. **与数据仓库的契约**：
   - 插件只认 `index.json` 与 `weekly/*.json` 的稳定契约，数据仓库内爬虫的具体实现（Python 或 Node）不影响插件正常运行。

---

## 6. 后续实施阶段与排期

1. **第一阶段：插件核心逻辑**
   - 搭建标准 Koishi 插件工程结构。
   - 接入数据源拉取与缓存服务（本地假数据/在线真实数据测试）。
   - 实现 `周榜`（最新）和 `周榜 <期号>` 文本渲染输出。
2. **第二阶段：增强检索与订阅**
   - 实现 `搜歌` 功能与轻量反向索引。
   - 实现定时检测最新期数并执行订阅群广播推送。
3. **第三阶段：可选卡片渲染与打包发布**
   - 接入 Puppeteer / Canvas 卡片排版。
   - 编写使用文档，发布至 npm / Koishi 插件市场。
