# BioStock 蔡P 生技雷達 - 專案完整架構

> 給 Claude Cowork / 任何協作者參考的單頁說明文件
>
> 建立日期：2026-05-18
> 維護：rebiocadd
> 線上版：https://rebiocadd.github.io/biotech-timeline/
> GitHub Repo：https://github.com/rebiocadd/biotech-timeline

---

## 一、專案目的

追蹤台灣 26 家生技公司 2026 年的臨床催化事件（解盲 / 期中分析 / 授權 / 藥證 / 期別推進）、股價、籌碼（千張大戶 / 集保戶分散）、現金部位（4 年度），並以 AI 動態評分整合所有訊號，協助投資人決策時程與佈局。

**核心理念**（孫子兵法 : 兵馬未動，糧草先行）：
從股東結構與千張異動觀察「糧草」是否暗中調動，預測解盲事件前的籌碼布局。

---

## 二、技術棧

| 層 | 技術 | 說明 |
|---|---|---|
| **前端** | 純 HTML + CSS + JavaScript (vanilla)，無框架 | 單頁 `index.html`，所有功能用 fetch + DOM |
| **資料儲存** | JSON 檔案（直接放 repo） | 無資料庫，每個檔案對應一張表格 |
| **後端腳本** | Python 3.11 | 6 支 `update_*.py` 腳本 |
| **自動化** | GitHub Actions | 4 條 cron 排程 |
| **部署** | GitHub Pages | 從 `main` 分支根目錄直接 serve |
| **網域** | `rebiocadd.github.io/biotech-timeline/` | 預設 GitHub Pages |
| **資料源** | FinMind / yfinance / TWSE / TPEX / TDCC / FinMind 等 | 詳見 `DATA_SEARCH_MEMO.md` |

---

## 三、檔案結構

```
biotech-timeline/
├── README.md                       專案說明（user 視角）
├── PROJECT_ARCHITECTURE.md         本文件（dev/Cowork 視角）
├── DATA_SEARCH_MEMO.md             資料源追查 SOP
├── SCORING_ENGINE.md               評分引擎設計說明
├── .gitignore
├── .github/
│   └── workflows/
│       └── update-prices.yml       4 個自動化 job
├── config/
│   └── scoringWeights.json         評分權重設定（可調整）
│
├── 【前端】
├── index.html                      唯一前端檔案（4000+ 行，含 CSS + JS + HTML）
│
├── 【資料 JSON（前端 fetch 讀取）】
├── date.json                       26 家公司 + 2026 events 主資料（最重要）
├── scores.json                     動態評分結果（7 模組 + 風險閘）
├── news_status.json                新聞掃描結果（每天更新）
├── holders.json                    千張大戶最新快照
├── holders_history.json            千張大戶歷史（3+ 週）
├── cashflow.json                   4 年現金部位（2023/2024/2025/2026）
├── status.json                     各腳本最後執行時間（徽章用）
│
└── 【後端 Python 腳本】
    ├── _status_helper.py           更新 status.json 的共用模組
    ├── update_prices.py            抓股價（每日 09:00, 15:00）
    ├── update_news.py              掃描新聞（每天 08:00）
    ├── update_highlights.py        新聞→自動標記 highlights
    ├── update_scores.py            重算動態評分
    ├── update_holders.py           抓 TDCC 千張資料（週六 10:00）
    └── update_cashflow.py          抓 FinMind 現金部位（週六 10:00）
```

---

## 四、資料流（重要！）

```
┌──────────────────┐
│   GitHub Actions │
│   4 條 cron      │
└─────────┬────────┘
          │
          ├─→ 每日 09:00/15:00 ─→ update_prices.py ─→ date.json (price/change/history)
          │
          ├─→ 每天 08:00 ──→ update_news.py ──────→ news_status.json
          │                ↓
          │              update_highlights.py ────→ date.json (highlights 標記)
          │                ↓
          │              update_scores.py ────────→ scores.json
          │
          └─→ 週六 10:00 ─→ update_holders.py ─────→ holders.json + holders_history.json
                          ↓
                        update_cashflow.py ────────→ cashflow.json
                          ↓
                        update_scores.py ──────────→ scores.json (週度重算)

          每個腳本完成後 → _status_helper.py → status.json (更新時間戳)

前端 index.html：
   fetch() ←── date.json / scores.json / holders_history.json / cashflow.json / news_status.json / status.json
   渲染所有表格
```

---

## 五、頁面區塊 × 資料源 × 自動化 對照表

| # | 頁面區塊 | 資料源 JSON | 由哪個 .py 更新 | 排程 |
|---|---|---|---|---|
| 1 | 🗓️ 主時程表（公司事件矩陣） | `date.json` | events 部分手動，price 部分 `update_prices.py` | 平日 09:00, 15:00 |
| 2 | 🔵 今年解盲（2026） | `date.json` | （同上）| 平日 09:00, 15:00 |
| 3 | 🎯 AI 動態訊號評估引擎 | `scores.json` | `update_scores.py` | 每日 08:00 + 週六 10:00 |
| 4 | 💡 AI 全自動市場訊號解讀 | `holders_history.json` + `news_status.json` | `update_holders.py` + `update_news.py` | 週六 10:00 + 每日 08:00 |
| 5 | ⭐ 本週值得注意 | `date.json` (highlightThisWeek) | `update_highlights.py` | 每日 08:00 |
| 6 | 🏦 集保戶持股統計 | `holders_history.json` | `update_holders.py` | 週六 10:00 |
| 7 | 🏆 26 家總股東排行（三週快照） | `holders_history.json` | `update_holders.py` | 週六 10:00 |
| 8 | 💰 26 家現金流餘額排行（4 年度） | `cashflow.json` | `update_cashflow.py` | 週六 10:00 |

---

## 六、`date.json` 結構（核心資料）

```json
[
  {
    "section": "上市公司 (6 家)",
    "companies": [
      {
        "code": "6446",
        "name": "藥華藥",
        "market": "listed",                       // listed=上市 / otc=上櫃 / emerging=興櫃
        "website": "https://www.pharmaessentia.com/",
        "strategy": "biosimilar",                 // 505b2 / biosimilar / cart / newform / nce
        "indication": "真性紅血球增多症",
        "target": "Ropeginterferon",
        "price": "1320.00",                       // 由 update_prices.py 更新
        "change": "-5.00",
        "priceDate": "05/16",
        "priceHistory": [                         // 240 個交易日（MA60/120/240 用）
          {"date": "05/15", "close": 1325.00}, ...
        ],
        "events": {                               // ★ 手動編輯 ★
          "q1": null | { event obj },
          "q2": { ... },
          "q3": { ... },
          "q4": { ... },
          "h2": { ... }                           // 下半年（Q3+Q4 通用事件）
        }
      }
    ]
  }
]
```

### 單個 event 物件可用欄位（全部選填）

```json
{
  "tag": "tag-resolve",                          // 必填：tag-resolve/tag-data/tag-license/tag-phase/tag-approval/tag-conference
  "label": "1b 解盲",                            // 必填：簡短標題
  "drug": "PS-001",                              // 藥物代號
  "detail": "...",                               // 詳細說明
  "status": "進行中",                            // 狀態文字
  "statusLabel": "已公布",                        // 狀態徽章

  // 投資觀察重點（事件卡點開後顯示）
  "catalystLevel": "高",                         // 高/中高/中/中低/低
  "catalystReason": "...",                       // 觀察重點完整說明
  "highlightThisWeek": true,                     // 是否進入「本週重點」
  "highlightReason": "...",                      // 本週重點原因
  "lastConfirmed": "2026/05/18",                 // 最後確認日

  // 三色徽章（顯示於「今年解盲」表格 TPIDB 連結下方）
  "tfdaUrl": "https://e-sub.fda.gov.tw/...",     // 🔵 藍：TPIDB / TFDA 案號
  "tfdaEndDate": "2027/12/31",                   // 法規最慢結束日
  "announcedNote": "2026/04/23 期中分析通過",     // 🟢 綠：已公布事件 + 日期
  "expectedDisclosureNote": "預計2026年Q2 公布解盲數據",  // 🟠 橘：公司指引時間

  // 投資亮點（事件卡顯示）
  "bonusFactors": [
    {"label": "機轉", "value": "全球首創 <em>...</em>"},
    ...
  ],

  // 來源（事件卡顯示）
  "sources": [
    {"label": "公開資訊觀測站", "url": "https://mops.twse.com.tw/mops/#/web/t146sb05?companyId=XXXX"}
  ],

  "note": "..."                                  // 警語/補充
}
```

---

## 七、修改情境 SOP

### 🎯 情境 A：加入一家新公司

1. 編輯 `date.json`，在對應 section（上市/上櫃/興櫃）的 `companies` 陣列加入新物件
2. 必填欄位：`code`, `name`, `market`, `events`（即使每季都 null 也要有）
3. commit + push
4. 自動跟進：
   - 下一次 09:00/15:00 排程 → 自動補股價
   - 下次週六 10:00 → 自動補千張 + 現金流
   - 下次 08:00 → 自動補新聞 + 評分

### 🎯 情境 B：更新某公司某季事件

1. 編輯 `date.json` 找到對應 `companies[X].events.{q1/q2/q3/q4/h2}`
2. 修改物件內容
3. commit + push
4. 1-2 分鐘後 GitHub Pages 自動部署

### 🎯 情境 C：新增「已公布」徽章

在 event 物件加入：`"announcedNote": "YYYY/MM/DD 事件描述"` → 自動顯示綠色 ✅ 徽章

### 🎯 情境 D：新增「預計公布」徽章

在 event 物件加入：`"expectedDisclosureNote": "預計2026年Q? 解盲"` → 自動顯示橘色 📅 徽章

### 🎯 情境 E：調整評分權重

編輯 `config/scoringWeights.json`，下次評分跑時生效。

### 🎯 情境 F：強制觸發自動化

到 GitHub Actions 頁面 → 選 workflow → Run workflow → 選 task (prices/news/holders/all)

---

## 八、GitHub 設定

| 設定 | 值 |
|---|---|
| **Repo URL** | https://github.com/rebiocadd/biotech-timeline |
| **預設分支** | `main` |
| **GitHub Pages 來源** | `main` 分支根目錄 |
| **Pages URL** | https://rebiocadd.github.io/biotech-timeline/ |
| **權限** | Public（GitHub Pages 必須 public 或 GitHub Pro 才能 private） |
| **Workflow 權限** | `contents: write`（允許 Action 自動 commit） |
| **Workflow 檔** | `.github/workflows/update-prices.yml` |

---

## 九、自動化排程（Cron）

```yaml
# .github/workflows/update-prices.yml
on:
  schedule:
    - cron: '0 1 * * 1-5'   # 平日 09:00 TST → 早盤股價
    - cron: '0 7 * * 1-5'   # 平日 15:00 TST → 收盤股價
    - cron: '0 0 * * *'     # 每天 08:00 TST → 新聞 + highlights + scores
    - cron: '0 2 * * 6'     # 週六 10:00 TST → holders + cashflow + scores
  workflow_dispatch:        # 也允許手動觸發
```

每週自動執行次數約 **18 次 commits**。

---

## 十、資料源（外部依賴）

| 來源 | 用於 | 配額 | 備援 |
|---|---|---|---|
| **FinMind API** | 現金部位 4 年 | 5000/day 免費 | yfinance |
| **yfinance** | 股價、營業現金流 | 無限 | TWSE 官方 |
| **TWSE API** | 上市股價 | 無限 | Yahoo Finance |
| **TPEX API** | 上櫃股價 | 無限 | Yahoo Finance |
| **玩股網 wantgoo** | 股價交叉驗證 | 無限 | (備援) |
| **TDCC 集保所** | 千張大戶分布 | 每週六更新 | (無備援) |
| **Google News** | 新聞掃描 | 無限制 | (無備援) |

詳細追查 SOP 見 `DATA_SEARCH_MEMO.md`。

---

## 十一、常見維護任務

### 查 GitHub Action 是否成功
```
https://github.com/rebiocadd/biotech-timeline/actions
```

### 本機跑單一腳本
```bash
cd biotech-timeline/
python update_prices.py        # 抓股價
python update_news.py          # 掃新聞
python update_holders.py       # 抓千張
python update_cashflow.py      # 抓現金
python update_scores.py        # 算評分
```

### 本機檢視變更
```bash
git diff date.json
git diff scores.json
```

### 推送到 GitHub
```bash
git add .
git commit -m "說明"
git push origin main
```

---

## 十二、已知限制與注意事項

1. **興櫃公司沒有 Q1/Q3 季報**（法規不要求），所以 `cashflow.json` 中興櫃公司 2026 Q1 都會是 `null`，要等 9 月半年報。
2. **GitHub Actions cron 可能延遲 5-30 分鐘**（GitHub 排程系統流量決定）。
3. **GitHub Pages 部署有 1-2 分鐘延遲**（push 後不會立即更新）。
4. **`events` 物件目前手動編輯**（沒做 LLM 自動抽取，避免幻覺風險）。
5. **`date.json` 內容更動時要小心 JSON 格式**（少一個逗號全頁就 fetch 失敗）。

---

## 十三、給協作者（Cowork / 其他人）的速查表

| 我想... | 我該改哪個檔案 |
|---|---|
| 更新某公司某季事件文字 | `date.json` → `companies[X].events.{q?}` |
| 加新公司 | `date.json` → 對應 section.companies |
| 調整評分權重 | `config/scoringWeights.json` |
| 改前端樣式/版面 | `index.html` |
| 改自動化排程時間 | `.github/workflows/update-prices.yml` |
| 看資料抓取的歷史問題 | `DATA_SEARCH_MEMO.md` |
| 看評分引擎邏輯 | `SCORING_ENGINE.md` 或 `update_scores.py` |

---

## 十四、聯絡與授權

- 維護者：rebiocadd
- 授權：本專案僅供研究與追蹤參考，不構成投資建議
- 線上版每天自動更新，無需手動 deploy
