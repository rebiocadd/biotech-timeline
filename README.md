# 蔡P生技雷達 · Taiwan Biotech Catalyst Radar

> **線上版**：<https://rebiocadd.github.io/biotech-timeline/>

追蹤 25 家台灣生技股的 2026 年臨床試驗、解盲、藥證、授權與催化事件。整合股價、新聞、千張大戶集保資料，提供即時投資解讀。

---

## 📋 目錄

- [專案概覽](#-專案概覽)
- [自動化排程](#-自動化排程)
- [檔案結構](#-檔案結構)
- [資料 schema](#-資料-schema)
- [前端功能](#-前端功能)
- [公司清單](#-公司清單)
- [Telegram Bridge](#-telegram-bridge)
- [腳本與工具](#-腳本與工具)
- [開發筆記](#-開發筆記)

---

## 🎯 專案概覽

| 項目 | 內容 |
|------|------|
| **託管** | GitHub Pages (靜態網頁) |
| **後端** | Python 3.11 + GitHub Actions cron |
| **前端** | 純 HTML + CSS + JavaScript（無框架） |
| **公司數** | 25 家（上市 6 + 興櫃 19） |
| **時區** | 全部 UTC+8 (Asia/Taipei) |
| **資料來源** | Yahoo Finance、TWSE/TPEX、玩股網、TDCC 集保、Google News RSS、公開資訊觀測站 |

---

## ⏰ 自動化排程

GitHub Actions workflow: `.github/workflows/update-prices.yml`

| 任務 | 頻率 | 時間（UTC+8） | 腳本 | 寫入檔案 |
|------|------|---------------|------|---------|
| 💰 **股價** | 平日 (一~五) ×2 | 09:00 / 15:00 | `update_prices.py` | `date.json` (price/change/priceDate/**priceHistory**) |
| 📡 **新聞掃描** | 每日 | 08:00 | `update_news.py` | `news_status.json` |
| ⭐ **自動標記** | 跟在新聞後 | 08:00+ | `update_highlights.py` | `date.json` (highlightThisWeek/_autoSource) |
| 🏦 **集保戶持股** | 每週六 | 10:00 | `update_holders.py` | `holders.json`, `holders_history.json` |

所有腳本都會更新 `status.json` 記錄最後執行時間。

### 排程觸發機制

- **概念**：三個 jobs (`update-prices`, `update-news`, `update-holders`) 依 cron 觸發
- **依賴順序**：news job `needs: update-prices`，holders job `needs: update-news` → 避免並行 push 衝突
- **失敗保護**：每個 job 有 `pull --rebase` + 5 次 retry 迴圈
- **手動觸發**：GitHub Actions UI → `workflow_dispatch` → 選擇 task

---

## 📂 檔案結構

```
biotech-timeline/                # GitHub repo root
├── index.html                   # 主網頁（含所有 CSS / JS）
├── date.json                    # 主要資料（25 家公司 + 事件）
├── holders.json                 # 本週千張大戶 + 15 等級
├── holders_history.json         # 多週歷史 snapshot（最多 52 週）
├── news_status.json             # 每日新聞掃描結果
├── status.json                  # 各任務最後執行時間
├── update_prices.py             # 股價更新（雙來源驗證 + 5日歷史）
├── update_news.py               # Google News RSS 掃描
├── update_highlights.py         # 自動標記 highlightThisWeek
├── update_holders.py            # TDCC 集保戶 15 等級抓取
├── _status_helper.py            # 共用 status.json 寫入工具
├── .github/
│   └── workflows/
│       └── update-prices.yml    # GitHub Actions cron 設定
└── README.md                    # 本檔
```

### 外部相關檔案（不在 repo 中）

```
D:\AI-agent\AI-claude\BioStock\
├── telegram_bridge.ps1          # PowerShell + Win32 Telegram 橋接
└── start_bridge.bat             # 開機自動啟動腳本

C:\Users\TKCPC\AppData\Roaming\Microsoft\Windows\
└── Start Menu\Programs\Startup\
    └── TelegramBridge.bat       # 自動啟動連結（複製自 start_bridge.bat）
```

---

## 📊 資料 schema

### `date.json`

```json
[
  {
    "section": "上市公司",
    "companies": [
      {
        "code": "6446",
        "name": "藥華藥",
        "market": "listed",
        "website": "https://hq.pharmaessentia.com/tw",
        "strategy": "newform",         // nce|505b2|biosimilar|cart|newform
        "indication": "ET / PV / MPN",
        "target": "PEG-IFN-α 干擾素",
        "price": "782.00",
        "change": "+5.63",
        "priceDate": "05/15",
        "priceHistory": [              // 近 5 個交易日（Yahoo 來源）
          {"date":"05/11","close":706.0},
          {"date":"05/12","close":711.0},
          {"date":"05/13","close":782.0},
          {"date":"05/14","close":782.0},
          {"date":"05/15","close":782.0}
        ],
        "events": {
          "q1": null,
          "q2": {
            "tag": "tag-approval",     // 事件類型 (見下表)
            "label": "台灣ET藥證核准",
            "drug": "Ropeg",
            "detail": "...",
            "status": "已核准",        // 自動推測或人工
            "statusLabel": "已公布",   // 5 色狀態
            "catalystLevel": "高",     // 高|中高|中|中低|低
            "catalystReason": "...",
            "highlightThisWeek": true,
            "highlightReason": "...",
            "lastConfirmed": "2026/05/15",
            "sources": [
              {"label":"衛福部 TFDA","url":"..."},
              {"label":"公開資訊觀測站","url":"..."}
            ],
            "bonusFactors": [          // 投資亮點（藥祇生醫 q2 有）
              {"label":"1a 數據","value":"健康人 <em>67% 血糖下降</em>..."}
            ]
          },
          "q3": {...},
          "q4": null,
          "h2": {...}
        }
      }
    ]
  }
]
```

#### 事件類型 (event.tag)

| tag | 意義 | 顏色 |
|-----|------|------|
| `tag-resolve` | 🔵 解盲／數據讀出 | cyan |
| `tag-data` | 🟣 試驗進度 | purple |
| `tag-license` | 🟢 授權／合作 | green |
| `tag-phase` | 🟠 期別推進 | orange |
| `tag-approval` | 🔴 藥證／核准 | red |
| `tag-conference` | 🌸 學術會議 | pink |

#### 五色狀態 (event.statusLabel)

| statusLabel | 顏色 | 意義 |
|-------------|------|------|
| 已公布 | 🟢 綠 | 已發生 / 已完成 |
| 預計中 | 🔵 藍 | 排程中 |
| 已進入審查 | 🟡 黃 | 法規審查中 |
| 延後待確認 | 🟠 橘 | 延期或補件 |
| 無新進度 | ⚪ 灰 | 目前無動態 |

#### 自動標記欄位 (event._autoSource)

- 有此欄位 → 標記由 `update_highlights.py` 自動產生（可被腳本覆蓋）
- 無此欄位 → 人工維護（腳本**永不覆蓋**）

---

### `holders.json` 與 `holders_history.json`

```json
{
  "curr_date": "05/08",
  "prev_date": "04/30",
  "data": [
    {
      "code": "6446",
      "name": "藥華藥",
      "curr_h": 53,                     // 千張大戶 本週人數
      "curr_s": 157271951,              // 千張大戶 本週股數
      "prev_h": 52,                     // 千張大戶 上週人數
      "prev_s": 155874000,              // 千張大戶 上週股數
      "total_s": 379924370,             // 總發行股數（合計行）
      "total_h": 46116,                 // 全公司總股東人數
      "prev_total_h": 46608,            // 上週總股東人數
      "levels": {                       // 15 個持股等級
        "1000k+":    {"curr_h":53,  "curr_s":157271951, "prev_h":52, "prev_s":155874000},
        "800-1000k": {"curr_h":17,  "curr_s":15262763,  "prev_h":18, "prev_s":...},
        "600-800k":  {...},
        "400-600k":  {...},
        "200-400k":  {...},
        "100-200k":  {...},
        "50-100k":   {...},
        "40-50k":    {...},
        "30-40k":    {...},
        "20-30k":    {...},
        "15-20k":    {...},
        "10-15k":    {...},
        "5-10k":     {...},
        "1-5k":      {...},
        "0-999":     {"curr_h":29187, "curr_s":3417714, ...}
      }
    }
  ]
}
```

`holders_history.json` 結構：

```json
{
  "weeks": [
    {
      "date": "05/08",
      "rawDate": "20260508",
      "data": [
        {
          "code": "6446", "name": "藥華藥",
          "h": 53, "s": 157271951,       // 向後相容（千張）
          "total_s": 379924370,
          "total_h": 46116,
          "levels": {
            "1000k+": {"h":53, "s":157271951},
            ...
          }
        }
      ]
    },
    {"date":"04/30", ...}
  ]
}
```

---

### `news_status.json`

```json
{
  "lastRun": "2026/05/15 23:25",
  "lastRunDate": "05/15",
  "freshDays": 14,
  "companies": {
    "6446": {
      "checked": "05/15",
      "news": [
        {
          "title": "藥華藥(6446) Ropeg於臺灣率先獲全球首張ET核准函...",
          "link": "https://news.google.com/rss/articles/...",
          "date": "05/13"
        }
      ]
    },
    "4147": {"checked":"05/15", "news":[]}
  }
}
```

---

### `status.json`

```json
{
  "prices":     {"lastRun":"2026/05/15 23:16", "lastRunDate":"05/15", "tz":"UTC+8"},
  "news":       {"lastRun":"2026/05/15 23:25", "lastRunDate":"05/15", "tz":"UTC+8"},
  "holders":    {"lastRun":"2026/05/16 10:30", "lastRunDate":"05/16", "tz":"UTC+8", "dataDate":"05/08"},
  "highlights": {"lastRun":"2026/05/16 00:40", "lastRunDate":"05/16", "tz":"UTC+8"}
}
```

---

## 🎨 前端功能

### 💡 投資解讀 (Auto-Signals)

位置：版面頂部（標籤圖例下方）

- 自動分析本週**總股東人數變化** Top 5
- **PINNED_SIGNALS** = `['7878']`（藥祇生醫永遠固定納入）
- 3 欄表格：公司｜變化｜可能原因（自動分析）
- 變化分級：
  - 大幅進場 (≥+500)
  - 持續累積 (+100~+499)
  - 緩步進場 (+10~+99)
  - 緩步減持 (-10~-99)
  - 散戶離場 (-100~-499)
  - 大幅離場 (≤-500)
- **可能原因** 自動分析優先序：
  1. 含催化關鍵字的近期新聞 (核准/藥證/解盲/期中分析/...)
  2. 最新一則新聞
  3. 任何季度的 `highlightReason`
  4. 任何季度的 `catalystReason` 第一句
  5. 任何季度的 `detail` 第一句
  6. 事件 `label` + `drug` 名稱
  7. 公司 `indication` 或 `target`
  8. `'資料載入中…'` 最終 fallback

### ⭐ 本週值得注意 (Highlights)

位置：投資解讀下方、時間軸上方

- 自動篩選 Top 6 重點事件（依催化強度評分）
- **規則**：當季 Q2 + 任何季度若被明確標記 (`highlightThisWeek:true`)
- 每張卡片 2 行版面：
  - 左側：公司名 + 事件 + 季度 + 觀察理由（單行省略）
  - 右側：近 5 日收盤價條帶（手機自動縮為 3 日）
  - 紅漲綠跌著色（相對前日）
- 點擊卡片自動滾到對應公司列

### 🏦 集保戶持股統計

15 個持股等級「工作區」（類 Excel tabs）：

| 等級 | 範圍 |
|------|------|
| ≥ 1M | 1,000,001+ 股（千張大戶）|
| 800k-1M | 800,001 ~ 1,000,000 |
| 600-800k | 600,001 ~ 800,000 |
| 400-600k | 400,001 ~ 600,000 |
| 200-400k | 200,001 ~ 400,000 |
| 100-200k | 100,001 ~ 200,000 |
| 50-100k | 50,001 ~ 100,000 |
| 40-50k | 40,001 ~ 50,000 |
| 30-40k | 30,001 ~ 40,000 |
| 20-30k | 20,001 ~ 30,000 |
| 15-20k | 15,001 ~ 20,000 |
| 10-15k | 10,001 ~ 15,000 |
| 5-10k | 5,001 ~ 10,000 |
| 1k-5k | 1,000 ~ 5,000 |
| < 1k | 1 ~ 999（零股族）|

表格欄位：
- 代號 / 公司（合併兩列顯示）
- 本週人數、上週人數、變化
- 本週持股、上週持股、變化
- **總股東人數**（含週變化 ▲▼）
- 總發行股數
- 該等級佔比%

可切換週次（歷史最多 52 週）、可排序、滑鼠橫向捲動。

### 🏆 25 家總股東排行

位置：集保戶持股表格下方

- 依本週 `total_h` 由多到少排序
- 左右兩欄：左 1-13 / 右 14-25
- 顯示排名、公司、總股東、週變化
- 自動同步千張資料更新

### 📡 狀態列徽章

頂部 3 個 pill：

- **💰 股價更新**：時間 + UTC+8 + 💹 25/25 家
- **📡 新聞掃描**：時間 + UTC+8 + 🆕 N 家
- **🏦 千張統計**：時間 + UTC+8 + 資料：MM/DD

---

## 🏢 公司清單

### 上市公司 (6 家)

| # | 公司 | 代號 | 策略 | 主要藥物 |
|:---:|------|:---:|:---:|--------|
| 1 | 中裕新藥 | 4147 | nce | TMB-365/380 (HIV) |
| 2 | 藥華藥 | 6446 | newform | Ropeg (MPN) |
| 3 | 康霈生技 | 6919 | nce | CBL-514 (局部減脂) |
| 4 | 順藥 | 6535 | nce | LT3001 (中風) |
| 5 | 逸達生技 | 6576 | 505b2 | FP-001 (兒童性早熟) |
| 6 | 智擎生技 | 4162 | 505b2 | PEP07/08 (腫瘤) |

### 興櫃公司 (19 家)

| # | 公司 | 代號 | 策略 | 主要藥物 |
|:---:|------|:---:|:---:|--------|
| 1 | 藥祇生醫 ⭐ | 7878 | nce | PS-001 (糖尿病) |
| 2 | 安成生技 | 6610 | 505b2 | AC-203 (EBS) |
| 3 | 鼎晉生技 | 7876 | newform | OBI-858 (醫美) |
| 4 | 漢康生技 | 7827 | nce | HCB101 (腫瘤) |
| 5 | 安立璽榮 | 7871 | nce | EI-1071 (神經) |
| 6 | 圓祥生技 | 6945 | nce | IBI302 (黃斑) |
| 7 | 竟天生技 | 6917 | nce | AP101 (麻醉) |
| 8 | 泰合生技 | 6467 | 505b2 | TAH3311 (抗血栓) |
| 9 | 仁新醫藥 | 6696 | nce | LS-008 (Stargardt) |
| 10 | 思捷優達 | 7829 | nce | YA-101 (MSA) |
| 11 | 醣聯 | 4168 | biosimilar | SPD8 (骨鬆) |
| 12 | 安基生技 | 7754 | nce | AJ201 (SBMA) |
| 13 | 宇越生醫 | 7902 | cart | UWC19 (B 細胞淋巴) |
| 14 | 昱厚生技 | 6709 | newform | AD17002 (氣喘) |
| 15 | 奧孟亞 | 7776 | biosimilar | ANY002 (GLP-1) |
| 16 | 生華科 | 6492 | nce | CX-5461 (腫瘤) |
| 17 | 沛爾生醫 | 6949 | cart | PL001 (B 細胞淋巴) |
| 18 | 長聖 | 6712 | cart | CAR001 (實體腫瘤) |
| 19 | 全福生技 | 6885 | nce | BRM421 (乾眼) |

⭐ = 投資解讀 PINNED_SIGNALS 固定觀察

---

## 📱 Telegram Bridge

### 用途

讓你在手機 Telegram 傳訊息 → 自動貼到電腦上的 Claude Code 視窗（執行於 Claude Desktop App 內）。

### 目前版本：**v9** ✅（2026/05/16 起穩定運作）

### 設定

- **Bot**: `@tsaiP_biotech_bot`
- **Token**: 寫死在 `telegram_bridge_v9.ps1`
- **Chat ID**: `1070699046`
- **核心技術**: PowerShell + Win32 API (SetForegroundWindow + AttachThreadInput + Alt-key 焦點重置) + wscript.shell SendKeys
- **腳本位置**: `D:\AI-agent\AI-claude\BioStock\telegram_bridge_v9.ps1`
- **Log 檔**: `D:\AI-agent\AI-claude\BioStock\bridge_log.txt`

### 🔑 關鍵設計決策（v9 確認）

| 議題 | 答案 |
|------|------|
| Claude Code 跑在哪？ | **Claude Desktop App 內建的 xterm.js 終端**（不是獨立的 Windows Terminal） |
| 貼上按鍵 | **`Ctrl+Shift+V`** (xterm.js 標準)，不是 Ctrl+V！ |
| 目標視窗 | `claude.exe` PID with MainWindowTitle `Claude` |
| 視窗狀態 | **絕對不可最小化**（否則 SendKeys 鍵盤事件無法抵達） |

### 自動啟動

| 檔案 | 位置 | 作用 |
|------|------|------|
| `start_bridge.bat` | `D:\AI-agent\AI-claude\BioStock\` | 啟動腳本（殺舊→啟新，視窗 NORMAL 不縮小） |
| `TelegramBridge.bat` | `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\` | Windows 開機自動執行 |

### Telegram 指令

| 指令 | 作用 |
|------|------|
| `/status` | 顯示 bot 線上 + 目標視窗 |
| `/help` | 列出所有指令 |
| `/log` | 顯示最近 25 行 bridge log（手機就能 debug） |
| 任何其他文字 | 自動注入到 Claude Code |

### 手動操作

```cmd
# 立即重啟橋接（會殺舊→啟新）
D:\AI-agent\AI-claude\BioStock\start_bridge.bat

# 檢查是否在跑
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
  Where-Object { $_.CommandLine -like '*telegram_bridge_v9*' -and $_.CommandLine -notlike '*-NonInteractive*' }

# 停止橋接
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
  Where-Object { $_.CommandLine -like '*telegram_bridge*' -and $_.CommandLine -notlike '*Stop-Process*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

# 讀 log
Get-Content D:\AI-agent\AI-claude\BioStock\bridge_log.txt -Tail 30
```

### ⚠️ 已知陷阱

- **絕對不能最小化視窗**：`wscript.shell SendKeys` 從最小化的 PowerShell 視窗送出時，鍵盤事件無法抵達目標
  - ✅ 正常視窗（可被遮蓋）
  - ❌ `/MIN` 啟動或按最小化按鈕
- **xterm.js 貼上必須用 Ctrl+Shift+V**：標準 Ctrl+V 在 xterm.js 視為輸入字元 `^V`，不會貼上
- **PowerShell 腳本內不可有中文字元**（cp950 編碼問題）→ 用 `[char]0x5B8C` 等 Unicode code point
- **不能有兩個 bridge 同時跑**（會競爭 Telegram getUpdates，造成行為錯亂）
- **Claude Desktop App ≠ Claude Code**：兩者共用 `claude.exe` 程序名，但桌面 App 主視窗才是注入目標（CLI 跑在裡面的 xterm.js panel）
- 完整 debug 歷程參見 `D:\AI-agent\AI-claude\BioStock\TELEGRAM_BRIDGE.md`

---

## 🛠️ 腳本與工具

### `update_prices.py`

**功能**：抓取每家公司股價

**資料來源**（雙來源交叉驗證）：
1. **Yahoo Finance** (`query1.finance.yahoo.com`) - 也提供 5 日歷史
2. **TWSE / TPEX** 官方 API
3. **玩股網** (`wantgoo.com`)

**驗證**：差異超過 3% 時警告，採用 Yahoo

**寫入**: `date.json` 的 `price`, `change`, `priceDate`, `priceHistory`

### `update_news.py`

**功能**：Google News RSS 掃描每家公司

**搜尋**：`{name} {code}` 例如 "藥華藥 6446"

**過濾**：
- 14 天內的新聞才算「新」
- 必須含臨床關鍵字（解盲/臨床/試驗/授權/...）

**寫入**: `news_status.json`

### `update_highlights.py`

**功能**：根據新聞自動標記 `highlightThisWeek`

**邏輯**：
1. 對每家公司計算「催化分數」
   - 強正面 (+10~+16)：核准、解盲成功、達主要終點、療效通過、期中分析通過
   - 正面 (+2~+7)：啟動、推進、合作、AACR/ASCO
   - 負面 (-5~-16)：失敗、未達標、駁回
2. 分數 ≥ 10 → 自動標記
3. 配對到最相關的事件（藥名/標籤/適應症匹配）
4. 寫入 `_autoSource` 欄位區分自動 vs 人工
5. **永不覆蓋人工標記**（沒有 `_autoSource` 的）

### `update_holders.py`

**功能**：從 TDCC 集保戶網站抓取 15 個持股等級

**API**: `https://www.tdcc.com.tw/portal/zh/smWeb/qryStock`

**特色**：
- 一次 HTML 響應解析 15 個等級 + 合計人數/股數
- 公司清單自動從 `date.json` 載入（不再寫死）
- fetch 失敗時保留上次資料（避免該公司消失）
- 同時寫入兩週 snapshot 到 `holders_history.json`

### `_status_helper.py`

**功能**：共用模組，更新 `status.json` 中各任務的最後執行時間

**用法**：
```python
from _status_helper import update_status
update_status("prices")
update_status("holders", {"dataDate": "05/08"})
```

---

## 📝 開發筆記

### 重要慣例

- **時區**：全部 UTC+8，由 `_status_helper.py` 統一處理
- **編碼**：所有 Python 腳本開頭都加：
  ```python
  try:
      sys.stdout.reconfigure(encoding="utf-8")
  except Exception:
      pass
  ```
  避免 Windows 主控台 cp950 無法顯示 emoji
- **JSON 修改**：用 Python `json.dump(..., ensure_ascii=False, separators=(',', ':'))` 緊湊格式
- **永不用 sed 改 JSON**：URL 中的 `&` 會破壞結構，改用 perl 或 Python

### 顏色慣例（台股）

- 🔴 紅 = 上漲 / 進場
- 🟢 綠 = 下跌 / 離場

### 重點 commit message 風格

```
功能名稱 (簡短描述)

技術細節：
- 改了什麼檔案
- 為什麼這樣改

預期效果：
- 使用者看到什麼變化
```

### 公司排序

兩個區段都有「pinned 前面 + 其他維持原序」邏輯：

**上市公司前 3**：中裕新藥 / 藥華藥 / 康霈生技
**興櫃公司前 7**：藥祇生醫 / 安成生技 / 鼎晉生技 / 漢康生技 / 安立璽榮 / 圓祥生技 / 竟天生技

調整順序的範例腳本：`reorder_listed.py` / `reorder_otc.py`（用過即刪除，可隨時重建）

### Race Condition 處理

`renderSignals()` 和 `renderRanking()` 同時依賴：
- `_hHistory`（千張資料）
- `window._companyMeta`（公司 metadata）
- `_newsStatus`（新聞）

由於兩個 `fetch` 並行，Promise.all 完成後若 `_hHistory` 已就緒 → 強制重新呼叫 `loadWeek(0)` 確保 signals/ranking 用完整資料重新渲染。

### 已知陷阱

1. TDCC 「合計」行的標籤是 `"合　計"`（中間是全形空白 U+3000）→ 判斷用 `'計' in cells[1]`
2. TDCC marker 「1,000-」必須帶 `-` 避免誤匹配 `1,000,001`
3. PowerShell `--%` stop-parsing 用來處理含特殊字元的 git 訊息
4. GitHub Actions 並行 push 衝突 → 用 `needs:` 序列化 + retry 迴圈
5. TPEX API 從 GitHub IP 偶爾抓不到 → Yahoo Finance 作為主要備援

---

## 📞 聯絡

- **Repo**: <https://github.com/rebiocadd/biotech-timeline>
- **Pages**: <https://rebiocadd.github.io/biotech-timeline/>
- **Owner**: Kevin Tsai

---

⚠️ **免責聲明**：本網站提供之臨床進度、解盲時間、藥證審查、千張大戶等資訊均為公開資訊整理與自動化分析，僅供參考，不構成任何投資建議。實際時間可能因收案進度、統計分析或主管機關審查而調整。投資人應自行評估風險並以公司正式公告為準。
