# 🤝 Hermes / Codex 接手指南 — BioStock 蔡P 生技雷達

> 本文檔給 Hermes（OpenAI Codex）或任何協作者一次性了解專案並可以接手。
>
> **TL;DR**：純前端 GitHub Pages 網站，追蹤 27 家台灣生技公司 2026 年臨床催化事件。6 個 Python 腳本透過 GitHub Actions cron 自動更新 6 個 JSON 資料檔，前端 `index.html` 用 fetch 讀取並渲染成 9 個資訊區塊。維護核心 = 維護 `date.json` 的事件文字，其餘全自動。

---

## 目錄

1. [專案概覽](#一專案概覽)
2. [技術棧 & GitHub 設定](#二技術棧--github-設定)
3. [檔案結構](#三檔案結構)
4. [資料流總覽](#四資料流總覽)
5. [9 個前端區塊詳述](#五9-個前端區塊詳述)
6. [6 個 Python 後端腳本](#六6-個-python-後端腳本)
7. [7 個 JSON 資料檔](#七7-個-json-資料檔)
8. [自動化排程 (GitHub Actions)](#八自動化排程-github-actions)
9. [外部資料源](#九外部資料源)
10. [SOP — 常見維護操作](#十sop--常見維護操作)
11. [已知 bug / 避坑指南](#十一已知-bug--避坑指南)
12. [未來擴充方向](#十二未來擴充方向)
13. [上手檢查清單（Hermes 第一天）](#十三上手檢查清單hermes-第一天)

---

## 一、專案概覽

| 項目 | 內容 |
|---|---|
| **專案名** | 蔡P 生技雷達（孫子兵法：兵馬未動，糧草先行）|
| **線上版** | https://rebiocadd.github.io/biotech-timeline/ |
| **GitHub Repo** | https://github.com/rebiocadd/biotech-timeline |
| **預設分支** | `main` |
| **語系** | 繁體中文（zh-TW）|
| **核心理念** | 追蹤台灣 27 家生技公司 2026 年臨床事件（解盲/期中分析/授權/藥證），透過 AI 整合催化、現金、籌碼、新聞訊號，輔助投資決策 |
| **目標使用者** | 生技股投資人（特別是會關注解盲節點的長線/中線投資者） |

### 為何叫「兵馬未動，糧草先行」？

- 兵馬（事件）= 解盲、藥證、授權等催化
- 糧草（現金 + 籌碼）= 公司能不能撐到解盲、千張大戶有沒有先佈局
- 投資邏輯：**從股東結構與千張異動觀察「糧草」是否暗中調動**，預測解盲事件前的籌碼布局

---

## 二、技術棧 & GitHub 設定

### 技術棧

| 層 | 技術 | 備註 |
|---|---|---|
| **前端** | 純 HTML + CSS + JavaScript (vanilla) | 無框架，`index.html` 約 2000 行（CSS + JS + HTML 全在一個檔案）|
| **資料儲存** | JSON 檔案直接放 repo | 無資料庫，每張表/區塊對應一個 JSON |
| **後端腳本** | Python 3.11 | 6 支 `update_*.py` 腳本 |
| **自動化** | GitHub Actions | `.github/workflows/update-prices.yml` 一個檔包含 3 個 cron job |
| **部署** | GitHub Pages | 從 `main` 分支根目錄直接 serve |
| **CI 權限** | `contents: write` | 讓 Actions 自動 commit |
| **資料源 API** | FinMind / yfinance / TWSE / TPEX OpenAPI / TDCC / Google News | 詳見 [DATA_SEARCH_MEMO.md] |

### GitHub 設定

```
Repo URL:       https://github.com/rebiocadd/biotech-timeline
Pages URL:      https://rebiocadd.github.io/biotech-timeline/
Branch:         main (根目錄就是 GitHub Pages 來源)
Visibility:     Public (GitHub Pages 必須)
Workflow file:  .github/workflows/update-prices.yml
```

### Python 環境（GitHub Actions）

```yaml
python-version: '3.11'
# 套件透過 pip install --quiet 動態安裝
# 主要依賴：yfinance (cashflow 用，其他用 stdlib)
```

---

## 三、檔案結構

```
biotech-timeline/
├── README.md                       使用者面向說明（中文）
├── PROJECT_ARCHITECTURE.md         開發者架構文檔（中文，較詳細）
├── DATA_SEARCH_MEMO.md             資料源追查 SOP（MOPS/Goodinfo/FinMind 等）
├── SCORING_ENGINE.md               動態評分引擎設計說明
├── hermes.md                       ← 本文件（接手指南）
├── .gitignore
│
├── .github/
│   └── workflows/
│       └── update-prices.yml       自動化 workflow（3 個 cron job）
│
├── config/
│   └── scoringWeights.json         動態評分權重設定（可手動調整）
│
├── 【前端】
├── index.html                      唯一前端檔案（~2000 行）
│
├── 【資料 JSON（前端 fetch 讀取）】
├── date.json                       27 家公司 + 2026 events 主資料 ★最重要
├── scores.json                     動態評分結果（7 模組 + 5 風險閘）
├── provisions.json                 糧草先行評分 TOP N（7 維度）
├── news_status.json                每日新聞掃描結果
├── holders.json                    千張大戶最新快照
├── holders_history.json            千張大戶歷史（多週快照）
├── cashflow.json                   4 年度現金部位（2023/2024/2025/2026）
├── status.json                     各腳本最後執行時間（徽章用）
│
└── 【Python 後端腳本】
    ├── _status_helper.py           更新 status.json 的共用模組
    ├── update_prices.py            股價（每日平日 09:00 / 15:00）
    ├── update_news.py              新聞掃描（每天 08:00）
    ├── update_highlights.py        新聞自動標記 highlights（每天 08:00 接力）
    ├── update_scores.py            動態評分（每天 08:00 + 週六 10:00）
    ├── update_holders.py           TDCC 千張資料（週六 10:00）
    ├── update_cashflow.py          FinMind 現金部位（週六 10:00）
    └── update_provisions.py        糧草先行評分（每天 08:00 + 週六 10:00）
```

---

## 四、資料流總覽

```
┌──────────────────┐
│  GitHub Actions  │  (.github/workflows/update-prices.yml)
│  3 個 job × cron │
└─────────┬────────┘
          │
          ├─→ 平日 09:00/15:00 ──→ update_prices.py ──→ date.json (price/change/240日歷史)
          │                                                ↓
          │                                          (events 部分人工維護)
          │
          ├─→ 每天 08:00 ────→ update_news.py ──→ news_status.json
          │                ↓
          │              update_highlights.py ────→ date.json (highlights 標記)
          │                ↓
          │              update_scores.py ────────→ scores.json
          │                ↓
          │              update_provisions.py ────→ provisions.json
          │
          └─→ 週六 10:00 ─→ update_holders.py ─────→ holders.json + holders_history.json
                          ↓
                        update_cashflow.py ────────→ cashflow.json
                          ↓
                        update_scores.py ──────────→ scores.json (週度重算)
                          ↓
                        update_provisions.py ──────→ provisions.json (週度重算)

          每個腳本完成後 → _status_helper.py → status.json (更新時間戳)

前端 index.html：
   Promise.all([
     fetch('status.json'),
     fetch('news_status.json'),
     fetch('date.json'),
     fetch('cashflow.json'),
     fetch('scores.json'),
     fetch('provisions.json'),
   ]).then(...) → 渲染 9 個區塊
```

---

## 五、9 個前端區塊詳述

依網頁從上到下順序，每個區塊獨立 fetch 對應 JSON 資料：

### 1. 🔵 今年解盲（2026）
- **HTML id**: `upcoming-unblind-section`
- **JS function**: `renderUpcomingUnblind()`
- **資料源**: `date.json`（篩選 tag-resolve / tag-data + 解盲關鍵字 events）
- **表格欄位**: 季度 / 公司 / 藥物·階段 / 適應症·觀察重點 / 狀態 / 近 3 日收盤 / 關注
- **Sticky cols**: 季度 + 公司（手機橫向捲動時固定左 2 欄）
- **特殊徽章**:
  - 🔵 TPIDB/TFDA 連結（藍色，法規最慢結束日）
  - ✅ announcedNote（綠色，已公布事件）
  - 📅 expectedDisclosureNote（橘色，公司預計時間）
- **iOS Safari 修正**: 加 `will-change:transform` + `requestAnimationFrame` 重繪

### 2. 🎯 AI 自動化動態訊號評估引擎
- **HTML id**: `score-section`
- **JS function**: `renderScores()`
- **資料源**: `scores.json`
- **顯示**: 27 家公司卡片，每張顯示總分 + 7 模組柱狀圖 + 風險閘徽章
- **過濾標籤**: 關注/全部/≥80/≥65/高增資/短線過熱（預設「⭐ 關注」6 家）
- **WATCHLIST_CODES**: ['6446', '6610', '7878', '4147', '7871', '6945']（藥華藥/安成/藥祇/中裕/安立璽榮/圓祥）

### 3. 💡 AI 自動化市場訊號解讀
- **HTML id**: `signals-section`
- **JS function**: `renderSignals()`
- **資料源**: `holders_history.json` + `news_status.json`
- **顯示**: 散戶人數變化 Top N + AI 自動分析「可能原因」3 欄表格

### 4. 🌾 AI 評估糧草先行 TOP 5
- **HTML id**: `provisions-section`
- **JS function**: `renderProvisions()`
- **資料源**: `provisions.json`
- **顯示**: TOP 5 卡片 + 7 維度進度條 + 5 日股價條紋 + 智慧標籤
- **7 維度**: 催化迫近 25% + 股價窗口 17% + 臨床訊號 18% + 現金 9% + 新聞 9% + 成功機率 10% + 籌碼結構 12%
- **智慧標籤**: 期別風險（1b/1🟢 → 2🟡 → 3🔴）、上市難拉抬、細胞療法（自體/異體）、GLP-1 紅海、孤兒藥、股本水位

### 5. ⭐ 本週值得注意
- **HTML id**: `highlights-section`
- **JS function**: `renderHighlights()`
- **資料源**: `date.json`（篩 `highlightThisWeek: true` 的 events）
- **顯示**: 卡片清單，自動分析「可能原因」

### 6. 🗓️ 主時程表（上市 + 興櫃合一）
- **HTML class**: `timeline-rows` / 容器 id: `timeline`
- **JS function**: `renderData(timelineData)`
- **資料源**: `date.json`
- **顯示**: 27 家公司 × 5 季度（Q1/Q2/Q3/Q4/H2）矩陣網格
- **每格**: tag 顏色 + label + 藥物名
- **公司資訊欄**: 公司名 + 代號 + 市場標籤 + 策略徽章 + 適應症 + 標的 + 近 5 日收盤條紋
- **點擊事件格**: 彈出詳細 tooltip 卡片（含 catalystReason / bonusFactors / sources）

### 7. 🏦 27 家集保戶持股統計
- **HTML id**: `holders-section`
- **JS function**: `loadWeek(idx)` + `renderHolderRow()`
- **資料源**: `holders_history.json`
- **顯示**: 15 持股等級切換（≥1M 千張大戶 → 0-999 零股）+ 三週快照對比
- **欄位**: 公司 / 本週人數 / 上週人數 / 變化 / 持股 / 變化 / 總股東 / 總發行股數 / 佔比%
- **Sticky col 1**（公司名）橫向捲動時固定

### 8. 🏆 27 家總股東排行
- **HTML id**: `ranking-section` (table A `#ranking-tbl`)
- **JS function**: `renderHolderRanking()`
- **資料源**: `holders_history.json`
- **顯示**: 6 欄表格（# + 代號 + 公司 + 三週總股東人數）
- **三週日期**: 從 `_hHistory.weeks[0~2].date` 動態抓
- **Sticky cols**: 前 3 欄（#、代號、公司）

### 9. 💰 27 家現金流餘額排行
- **HTML id**: `ranking-section` 內 (table B `#cash-rank-tbl`)
- **JS function**: `renderCashRanking()`
- **資料源**: `cashflow.json`
- **顯示**: 7 欄表格（# + 代號 + 公司 + 2026/2025/2024/2023 現金餘額）
- **預設排序**: cash_2026 由大到小（取最新有資料的年度）
- **Sticky cols**: 前 3 欄

---

## 六、6 個 Python 後端腳本

### 1. `update_prices.py` — 股價更新（最頻繁）
- **何時跑**: 平日 09:00 / 15:00 TST
- **資料源優先序**: Yahoo Finance (主) → TWSE/TPEX 官方 (驗證) → 玩股網 (備援)
- **輸出**: 更新 `date.json` 的 `price`/`change`/`priceDate`/`priceHistory`（240 日交易日）
- **重要常數**:
  - `JSON_PATH`: `date.json`
  - `WARN_THRESHOLD`: 3.0%（雙來源差異警告）
  - `REQUEST_DELAY`: 0.8 秒（避免被封鎖）

### 2. `update_news.py` — 新聞掃描
- **何時跑**: 每天 08:00 TST
- **資料源**: Google News RSS
- **掃描 keywords**: 臨床、解盲、藥證、授權、收案、IDMC 等
- **輸出**: `news_status.json`（每家公司 7 天內新聞列表）

### 3. `update_highlights.py` — 自動標記 highlights
- **何時跑**: 每天 08:00 TST（在 news 之後）
- **邏輯**: 從新聞標題抽 keywords → 比對 events.label → 若匹配且分數高 → 設 `highlightThisWeek: true`
- **輸出**: 修改 `date.json` 中對應 events 的 `highlightThisWeek` 標記
- **重要**: 永不覆蓋人工設定的 `highlightThisWeek`（有 `_manual_highlight` 標記時）

### 4. `update_scores.py` — 動態評分引擎
- **何時跑**: 每天 08:00 + 週六 10:00 TST
- **7 個評分模組**:
  - catalyst（催化）: 25%
  - cashRunway（現金跑道）: 20%
  - pricePosition（股價位置）: 15%
  - trend（趨勢）: 10%
  - shareholder（籌碼）: 10%
  - newsSentiment（新聞情緒）: 10%
  - clinicalCredibility（臨床可信度）: 10%
- **5 個風險閘**: high_funding_risk / short_term_overheated / catalyst_too_far / clinical_credibility / dilution_risk
- **Score bands**: ≥80 高度研究 / ≥65 可觀察進場 / ≥50 觀察 / ≥35 風險升高 / <35 暫不考慮
- **重要修正紀錄**:
  - band gap bug（79.x 落到 0-34 fallback）已修：用 `>= min` 條件 + 排序
- **輸出**: `scores.json`

### 5. `update_holders.py` — TDCC 千張資料
- **何時跑**: 週六 10:00 TST
- **資料源**: TDCC 集保戶股權分散表（每週六公布）
- **抓取**: 15 個持股等級（≥1,000,001 股 → 1-999 股）
- **雙來源驗證**: 主源 + 備援源
- **輸出**: `holders.json`（最新快照）+ `holders_history.json`（累積歷史，保留最近 N 週）

### 6. `update_cashflow.py` — 現金部位
- **何時跑**: 週六 10:00 TST
- **資料源優先序**: FinMind (主) → yfinance (備援) → 既有 Goodinfo (沿用)
- **抓取**: 2023/2024/2025/2026 各年度 + Q1 2026 季度
- **智能合併**: FinMind 抓不到時自動沿用既有資料
- **依賴**: `pip install yfinance --quiet`（workflow 內動態裝）
- **輸出**: `cashflow.json`

### 7. `update_provisions.py` — 糧草先行評分（最新加入）
- **何時跑**: 每天 08:00 + 週六 10:00 TST
- **篩選**: 公司 events 中含 tag-resolve 或 tag-data + 解盲關鍵字
- **7 維度評分**:
  - imminence（催化迫近）25%
  - priceWindow（股價窗口）17%
  - clinical（臨床訊號）18%
  - cash（現金狀態）9%
  - newsHeat（新聞熱度）9%
  - successProb（成功機率）10%
  - shareStructure（籌碼結構）12%
- **特殊扣分/加分**:
  - 上市（market='listed'）→ shareStructure -20
  - 異體 CAR-T（high_allo）→ clinical -18, success -15
  - 自體 CAR-T（standard_cart）→ clinical -5, success -4
  - 口服 GLP-1 紅海 → clinical -12, success -10
  - 孤兒藥/罕病 → clinical +10, success +12
- **里程碑加分**:
  - 重大里程碑（IDMC/期中通過/DSMB/已進入審查）→ clinical +35, success +18
  - 收案完成 → clinical +35, success +14
  - 超前完成 → +8 / +8
  - 大規模收案：1000+人 +10/+8 / 800+ +8/+6 / 500+ +6/+4 / 300+ +4/+2 / 100+ +3/0 / 50+ +2/+1
- **輸出**: `provisions.json`

### `_status_helper.py` — 共用模組
- **用途**: 更新 `status.json` 對應欄位的 lastRun 時間戳
- **被誰呼叫**: 上述所有 `update_*.py` 結尾都 `from _status_helper import update_status; update_status("xxx")`

---

## 七、7 個 JSON 資料檔

### `date.json` ★ 最重要
**結構**：
```json
[
  {
    "section": "上市公司",
    "companies": [
      {
        "code": "6446",
        "name": "藥華藥",
        "market": "listed",         // listed / otc
        "website": "...",
        "strategy": "biosimilar",   // 505b2 / biosimilar / cart / newform / nce
        "indication": "...",
        "target": "...",
        "price": "1320.00",         // 由 update_prices.py 更新
        "change": "-5.00",
        "priceDate": "05/16",
        "priceHistory": [            // 240 個交易日
          {"date": "05/15", "close": 1325.00}, ...
        ],
        "events": {                 // ★ 人工維護
          "q1": null | {event obj},
          "q2": {...},
          "q3": {...},
          "q4": {...},
          "h2": {...}               // 下半年（Q3+Q4 通用）
        }
      }
    ]
  },
  {
    "section": "興櫃公司",
    "companies": [ ... ]
  }
]
```

### Event 物件完整欄位
```json
{
  "tag": "tag-resolve",                       // 必填：tag-resolve/tag-data/tag-license/tag-phase/tag-approval/tag-conference
  "label": "1b 解盲",                          // 必填
  "drug": "PS-001",
  "detail": "...",
  "status": "進行中",
  "statusLabel": "已公布",

  // 投資觀察重點
  "catalystLevel": "高",                       // 高/中高/中/中低/低
  "catalystReason": "...",
  "highlightThisWeek": true,
  "highlightReason": "...",
  "lastConfirmed": "2026/05/18",

  // 三色徽章
  "tfdaUrl": "https://e-sub.fda.gov.tw/...",  // 🔵 藍：TPIDB / TFDA
  "tfdaEndDate": "2027/12/31",
  "announcedNote": "2026/04/23 期中分析通過",   // 🟢 綠：已公布
  "expectedDisclosureNote": "預計2026年Q2",    // 🟠 橘：預計

  "bonusFactors": [
    {"label": "機轉", "value": "..."},
    ...
  ],
  "sources": [
    {"label": "公開資訊觀測站", "url": "https://mops.twse.com.tw/mops/#/web/t146sb05?companyId=XXXX"}
  ],
  "note": "..."
}
```

### 其他 JSON 結構

**`scores.json`** — 動態評分結果
```json
{
  "lastRun": "2026/05/20 08:00",
  "tz": "UTC+8",
  "companies": {
    "6446": {
      "code": "6446", "name": "藥華藥",
      "total": 82.5,
      "band": {"min": 80, "max": 100, "label": "高度研究名單", "color": "#10b981"},
      "components": {
        "catalyst": 100, "cashRunway": 100, "pricePosition": 95,
        "trend": 50, "shareholder": 60, "newsSentiment": 80, "clinicalCredibility": 100
      },
      "metadata": {...},
      "riskFlags": [...]
    }
  }
}
```

**`provisions.json`** — 糧草先行評分
```json
{
  "lastRun": "...", "tz": "UTC+8",
  "totalCompanies": 19,
  "candidates": [
    {
      "code": "7878", "name": "藥祇生醫",
      "provisionScore": 70.7,
      "components": {imminence, priceWindow, clinical, cash, newsHeat, successProb, shareStructure},
      "event": {quarter, tag, label, drug, daysUntil, expectedDate, highlightThisWeek},
      "priceStatus": {percentile, volatility, history5d, current},
      "shareCapital": {totalShares, label, short},
      "flags": {isListed, isCellTherapy, cellTherapyRisk, marketCompetition, isOrphan},
      "advice": "..."
    }
  ]
}
```

**`holders_history.json`** — 千張歷史
```json
{
  "weeks": [
    {
      "date": "05/15",
      "rawDate": "20260515",
      "data": [
        {
          "code": "...", "name": "...",
          "h": 56,             // 千張人數
          "s": 162732647,      // 千張持股
          "total_s": 379924370,// 總發行股數
          "total_h": 44236,    // 總股東
          "levels": {           // 15 個等級的人數+持股
            "1000k+": {"h": 56, "s": 162732647},
            "800-1000k": {"h": 17, "s": 15268888},
            ...
          }
        }
      ]
    }
  ]
}
```

**`cashflow.json`** — 現金部位
```json
{
  "lastRun": "...", "tz": "UTC+8",
  "companies": {
    "6446": {
      "cf_2025": {"period": "2025 年報", "operating_cf": 5277677000.0},
      "cash_2023": {"period": "2023年底", "value": 19666029000.0},
      "cash_2024": {...},
      "cash_2025": {...},
      "cash_2026": {"period": "2026 Q1底", "value": 24175410000.0},
      "source": "finmind+yfinance",
      "suffix": ".TW"
    }
  }
}
```

**`news_status.json`** — 新聞掃描
```json
{
  "lastRun": "...", "tz": "UTC+8",
  "companies": {
    "6446": {
      "count": 5,
      "news": [
        {"title": "...", "link": "...", "date": "2026/05/18"}
      ]
    }
  }
}
```

**`status.json`** — 各腳本時間戳
```json
{
  "prices":     {"lastRun": "2026/05/20 09:15", "lastRunDate": "05/20", "tz": "UTC+8"},
  "holders":    {"lastRun": "...", "dataDate": "05/15"},
  "news":       {...},
  "highlights": {...},
  "cashflow":   {...},
  "scores":     {...},
  "provisions": {...}
}
```

---

## 八、自動化排程 (GitHub Actions)

### `.github/workflows/update-prices.yml` — 唯一一個 workflow file

包含 **3 個 jobs**，每個 job 對應 cron 排程：

#### Job 1: `update-prices`
```yaml
cron: '0 1 * * 1-5'   # 平日 09:00 TST（早盤）
cron: '0 7 * * 1-5'   # 平日 15:00 TST（收盤）

執行：
  python update_prices.py
  git add date.json status.json
  git commit -m "自動更新股價..."
  git push（含 retry 5 次）
```

#### Job 2: `update-news`
```yaml
cron: '0 0 * * *'   # 每天 08:00 TST

執行：
  python update_news.py
  python update_highlights.py
  python update_scores.py
  python update_provisions.py
  git add news_status.json date.json status.json scores.json provisions.json
  git commit + push
```

#### Job 3: `update-holders`
```yaml
cron: '0 2 * * 6'   # 週六 10:00 TST

執行：
  python update_holders.py
  pip install yfinance --quiet
  python update_cashflow.py
  python update_scores.py
  python update_provisions.py
  git add holders.json holders_history.json cashflow.json scores.json provisions.json status.json
  git commit + push
```

### 排程一覽

| 時間 (TST) | 日期 | 動作 | 影響檔案 |
|---|---|---|---|
| 平日 09:00 | 週一-五 | 早盤股價 | `date.json` |
| 平日 15:00 | 週一-五 | 收盤股價 | `date.json` |
| 每天 08:00 | 每天 | 新聞 + highlights + 評分 + 糧草 | `news_status.json`, `date.json`, `scores.json`, `provisions.json` |
| 週六 10:00 | 週六 | 千張 + 現金 + 評分 + 糧草 | `holders.json`, `holders_history.json`, `cashflow.json`, `scores.json`, `provisions.json` |

**每週自動更新次數**：約 18 次 commits（含失敗重試實際更多）

### Workflow 內 retry 機制
```bash
for i in 1 2 3 4 5; do
  git pull --rebase origin main 2>/dev/null || git pull origin main || true
  python xxx.py
  git add ...
  if git diff --staged --quiet; then
    echo "No changes, skipping"; break
  fi
  git commit -m "..."
  if git push 2>&1; then
    echo "✅ Push success"; break
  fi
  echo "⚠️ Retry $i"
  git reset --soft HEAD~1
  git restore --staged .
  sleep 3
done
```

每個 push 最多重試 5 次（避免 GitHub 衝突）。

---

## 九、外部資料源

| 資料源 | 用於 | 配額 | 備援 | 備註 |
|---|---|---|---|---|
| **FinMind API** | 現金 4 年 + Q1 季度 | 5000/day 免費 | yfinance | 上市/上櫃 100% 覆蓋 |
| **yfinance** | 股價、營業現金流 | 無限 | TWSE 官方 | 通常落後 1-2 季 |
| **Yahoo Finance v8 chart** | 股價歷史 240 日 | 無限 | TWSE | range=1y |
| **TWSE OpenAPI** | 上市公司清單 + 損益表 | 無限 | - | t187ap03_L / t187ap14_L |
| **TPEX OpenAPI** | 上櫃公司清單 + 股價 | 無限 | - | mopsfin_t187ap03_O |
| **玩股網 wantgoo** | 股價交叉驗證 | 無限 | - | HTML 解析 |
| **TDCC 集保所** | 千張大戶分布 | 每週六更新 | - | 雙驗證 |
| **Google News RSS** | 新聞掃描 | 無限制 | - | 27 家公司 keyword 搜尋 |
| **MOPS 公開資訊觀測站** | 公司基本資料連結 | 反爬嚴重 | Goodinfo | URL 模式：`mops/#/web/t146sb05?companyId={code}` |
| **Goodinfo** | 興櫃公司財務（人工）| 反爬嚴重 | - | 需 Chrome MCP，目前以 FinMind 取代 |

詳細追查 SOP 見 `DATA_SEARCH_MEMO.md`（含 MOPS URL 從舊版 `web/...?stockNo=` 升級為 `#/web/...?companyId=` 的紀錄）。

---

## 十、SOP — 常見維護操作

### 🎯 SOP A：加入一家新公司（最重要 SOP）

**Step 1**：編輯 `date.json`
```json
// 在對應 section（上市/興櫃）的 companies 陣列加入
{
  "code": "XXXX",
  "name": "公司名",
  "market": "listed" or "otc",  // listed=上市 / otc=興櫃
  "website": "...",
  "strategy": "nce",            // 505b2/biosimilar/cart/newform/nce
  "indication": "...",
  "target": "...",
  "events": {
    "q1": null, "q2": null, "q3": null, "q4": null, "h2": null
  }
}
```

**Step 2**：立即跑 3 個腳本（讓新公司同時進 4 個獨立表格）
```bash
python update_cashflow.py        # → 💰 現金流排行
python update_holders.py         # → 🏦 集保戶 + 🏆 總股東排行
python update_scores.py          # → 🎯 動態評分
python update_provisions.py      # → 🌾 糧草先行
python update_prices.py          # (可選) 股價
```

**Step 3**：commit + push
```bash
git add date.json cashflow.json holders.json holders_history.json scores.json provisions.json status.json
git commit -m "新增 XXXX 第 N 家"
git push origin main
```

⚠️ **不立即跑會怎樣？** 使用者要等下次排程（最多 6 天）才會看到完整資料。

### 🎯 SOP B：更新某公司某季事件

1. 編輯 `date.json` → `companies[X].events.{q1/q2/q3/q4/h2}`
2. commit + push
3. 1-2 分鐘後 GitHub Pages 自動部署

### 🎯 SOP C：新增「已公布」綠色徽章

在 event 加 `"announcedNote": "YYYY/MM/DD 事件描述"`

### 🎯 SOP D：新增「預計公布」橘色徽章

在 event 加 `"expectedDisclosureNote": "預計2026年Q? 解盲"`

### 🎯 SOP E：調整動態評分權重

編輯 `config/scoringWeights.json` → 下次 `update_scores.py` 跑時生效

### 🎯 SOP F：強制觸發自動化

GitHub Actions 頁面 → 選 workflow → Run workflow → 選 task：
- `all`（跑全部）
- `prices`（只跑股價）
- `news`（只跑新聞）
- `holders`（只跑千張）

### 🎯 SOP G：本機開發測試

```bash
# 跑單一腳本
python update_prices.py
python update_news.py
# ...

# 啟動本機 HTTP server（前端必須透過 HTTP 才能 fetch）
python -m http.server 8000
# 開 http://localhost:8000/index.html

# 看變更
git diff date.json
git diff scores.json
```

---

## 十一、已知 bug / 避坑指南

### 1. **MOPS URL 升級坑**（已修）
- 舊版 `https://mops.twse.com.tw/mops/web/t146sb05?stockNo=XXXX&step=1` 已失效
- 新版 `https://mops.twse.com.tw/mops/#/web/t146sb05?companyId=XXXX`（注意 `#/`）

### 2. **興櫃公司沒有 Q1/Q3 季報**
- 法規不要求，FinMind 對興櫃公司 cash_2026 永遠 null
- 要等 Q2 半年報（約 8-9 月）

### 3. **GitHub Actions cron 可能延遲**
- GitHub 官方文件說明：cron schedule 可能延遲 5-15 分鐘以上
- 流量大時延遲 1-3 小時
- 看 `status.json` 的 lastRun 比 cron 預期晚是正常的

### 4. **GitHub Pages 部署延遲**
- push 後 1-2 分鐘才會更新
- 偶爾要等 5 分鐘

### 5. **JSON 格式錯誤會讓整頁 fetch 失敗**
- `date.json` 改完後一定要本機 `python -c "import json; json.load(open('date.json','r',encoding='utf-8'))"` 驗證
- 少一個逗號全頁就崩

### 6. **`events` 目前手動編輯**
- 沒做 LLM 自動抽取（避免幻覺）
- 改進方向：開發「新聞觸發 → 提示待補事件」自動化（不直接寫，只提示）

### 7. **iOS Safari sticky 圖層漏畫**（已修）
- sticky cells 偶爾消失，碰一下又出現
- 解法：CSS `will-change:transform` + `transform:translateZ(0)` + JS `requestAnimationFrame` 強制重繪

### 8. **Score band gap bug**（已修）
- 79.x 因為落在 79-80 gap 而被歸到「暫不考慮」(0-34)
- 解法：改用「>= min」邏輯 + 排序高到低取第一個符合

### 9. **catalyst 滿分集中問題**（已修）
- 之前 11/27 家公司 catalyst 都是 100，無區辨度
- 解法：base weights 下調 + proximity 過去事件特殊處理 + announcedNote 折扣

### 10. **Roman 數字（IIa/IIb/III）偵測**（已修）
- Python regex `\b` 對中文邊界判斷不正確（中文是 word char）
- 解法：用具體字串匹配 `'IIa期'` / `'Ⅱa期'` 等

### 11. **本地開發必須用 HTTP server**
- 直接開 `index.html` 用 `file://` 協議會被 CORS 擋住 fetch
- 必用 `python -m http.server 8000`

### 12. **commit 失敗的 retry 邏輯**
- workflow 內已有 5 次 retry
- 若還是失敗看 GitHub Actions 紀錄

### 13. **`config/scoringWeights.json` 編碼問題**
- 有些 keys 含中文（如 "3期"）
- 改完後一定要驗證 JSON 合法性

---

## 十二、未來擴充方向

### 短期（≤ 1 個月）
- [ ] 加入「⭐ 本週重點」改名為「⭐ 本週熱點」（語意更精準）
- [ ] 新增 events 自動標記建議（從新聞 + 標題 → 建議 user 編輯）
- [ ] 主時程表加篩選（按 catalystLevel）

### 中期（1-3 個月）
- [ ] 加入「中期佈局 TOP 5」（涵蓋 180-365 天事件）
- [ ] AI 評分歷史趨勢圖（每天 snapshot scores.json，畫趨勢）
- [ ] 「股價 vs 評分」散點圖
- [ ] 自動化「Goodinfo 興櫃公司現金流補抓」（用 Chrome MCP）

### 長期（≥ 3 個月）
- [ ] 從新聞稿 LLM 抽取結構化 events（有人工審核）
- [ ] PWA（離線可看 + 推播通知）
- [ ] 訂閱制（個別 watchlist 推播）
- [ ] 加入國際生技股對比（NASDAQ 同類公司）

---

## 十三、上手檢查清單（Hermes 第一天）

### 第一小時：環境理解
- [ ] 讀完本文件 `hermes.md`（你正在讀）
- [ ] clone repo: `git clone https://github.com/rebiocadd/biotech-timeline.git`
- [ ] 開 `index.html` 用 `python -m http.server 8000` 然後 `http://localhost:8000`
- [ ] 走訪線上版：https://rebiocadd.github.io/biotech-timeline/

### 第二小時：資料理解
- [ ] 讀 `date.json` 第一家公司（藥華藥 6446）的完整 event 結構
- [ ] 看 `scores.json` 該公司的評分 + 7 模組分數
- [ ] 看 `cashflow.json` 該公司 4 年現金部位
- [ ] 看 `holders_history.json` 該公司千張歷史
- [ ] 看 `provisions.json` TOP 5 是誰、為什麼

### 第三小時：自動化理解
- [ ] 讀 `.github/workflows/update-prices.yml`
- [ ] 在 GitHub Actions 頁面看過往跑過的 workflow runs
- [ ] 看 `status.json` 各腳本最後跑的時間

### 第四小時：腳本理解
- [ ] 開 `update_prices.py` 看主流程
- [ ] 開 `update_scores.py` 看 7 個評分模組
- [ ] 開 `update_provisions.py` 看糧草先行邏輯
- [ ] 看 `_status_helper.py`（最短的）

### 第五小時：實際操作
- [ ] 本機跑 `python update_prices.py`
- [ ] 看 `git diff date.json` 看抓到什麼
- [ ] **不要 commit**（除非任務要求）
- [ ] 若有要做的修改任務，先看相關 JSON / Python 結構再下手

### 第一週：常見任務
- [ ] 加入一家新公司（依 SOP A）
- [ ] 更新某公司 events（依 SOP B）
- [ ] 加 announcedNote 徽章（依 SOP C）
- [ ] 看 console 開發者工具的 fetch 流程

### 重要原則
1. **絕不直接編輯股價/評分等自動生成的 JSON**（會被自動覆蓋）
2. **`date.json` 改 events 部分前先複製一份備份**
3. **commit message 用中文 + emoji**（符合既有風格）
4. **新增公司一定要跑 4 個腳本**（不然會缺資料）
5. **JSON 改完後本機驗證 `python -c "import json; json.load(open('xxx.json','r',encoding='utf-8'))"`**

---

## 附錄

### 相關文件
- `README.md` — 使用者面向（中文）
- `PROJECT_ARCHITECTURE.md` — 開發者架構（部分內容與本文件重疊）
- `DATA_SEARCH_MEMO.md` — 資料源追查 SOP
- `SCORING_ENGINE.md` — 動態評分引擎詳述

### 聯絡資訊
- 維護者：rebiocadd（GitHub）
- 授權：本專案僅供研究與追蹤參考，不構成投資建議

### 版本紀錄
- 2026-05-20 v1.0：建立本文件，9 個前端區塊定稿，27 家公司

---

**Welcome aboard, Hermes! 🤝**

讀完本文件，你應該已經能：
1. 知道專案在做什麼、為誰做、怎麼運作
2. 知道每個 JSON 對應哪個區塊
3. 知道每個 Python 腳本什麼時候跑、產出什麼
4. 知道加新公司、改事件的標準流程
5. 知道哪些坑已被填過、哪些地方還能擴充

若還有任何不清楚的地方，最佳查詢順序：
1. 先看本文件對應章節
2. 再看 `PROJECT_ARCHITECTURE.md` / `DATA_SEARCH_MEMO.md` / `SCORING_ENGINE.md`
3. 直接看對應 Python 腳本的 docstring
4. 開 GitHub Issues 問前任維護者
