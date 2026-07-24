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
├── 【科學展示卡 3D／2D 結構資產（index.html 內嵌 viewer 讀取）】
├── spin/
│   ├── 9qcm.pdb.gz                 實驗結構：RCSB PDB 9QCM（B1 型 14 鏈 L-PTC）
│   └── af_complex.pdb.gz           AlphaFold 組裝：5 蛋白單鏈預測 + 疊合成 14 鏈
├── bont_ptc_3d.jpg                 實驗複合體 3D 靜態海報（poster fallback）
├── bont_af_3d.jpg                  AlphaFold 14 鏈 3D 靜態海報
├── tinlarebant.svg                 仁新 Tinlarebant 2D 小分子結構
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
    ├── update_prices.py            抓股價（每日 06:00, 15:00）
    ├── update_news.py              掃描新聞（每天 06:00）
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
          ├─→ 每日 06:00/15:00 ─→ update_prices.py ─→ date.json (price/change/history)
          │
          ├─→ 每天 06:00 ──→ update_news.py ──────→ news_status.json
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

> 共 **8 個獨立區塊**，依照頁面實際從上到下顯示順序排列。
> 「🗓️ 主時程表」內含「上市公司」「興櫃公司」兩段，但屬同一個網格元件，算 1 個區塊。

| # | 區塊（HTML 順序） | 資料源 JSON | 由哪個 .py 更新 | 自動排程 |
|---|---|---|---|---|
| 1 | **🔵 今年解盲（2026）** | `date.json` (篩 tag-resolve / tag-data) | events 手動 + `update_prices.py` 補股價 | 平日 06:00, 15:00 |
| 2 | **🎯 AI 自動化動態訊號評估引擎** | `scores.json` | `update_scores.py`（讀 date+holders+cashflow+news 整合）| 每日 06:00 + 週六 10:00 |
| 3 | **💡 AI 全自動市場訊號解讀** | `holders_history.json` + `news_status.json` | `update_holders.py` + `update_news.py` | 週六 10:00 + 每日 06:00 |
| 4 | **⭐ 本週值得注意** | `date.json` (`highlightThisWeek:true` 事件) | `update_highlights.py` | 每日 06:00 |
| 5 | **🗓️ 主時程表**（上市 + 興櫃合一網格）| `date.json` (events 主表 + price/change/history)| events 手動 + `update_prices.py` 補股價 | 平日 06:00, 15:00 |
| 6 | **🏦 集保戶持股統計**（15 持股等級切換）| `holders_history.json` | `update_holders.py` | 週六 10:00 |
| 7 | **🏆 27 家總股東排行**（三週快照） | `holders_history.json` | `update_holders.py` | 週六 10:00 |
| 8 | **💰 27 家現金流餘額排行**（4 年度）| `cashflow.json` | `update_cashflow.py`（FinMind 主 + yfinance 備）| 週六 10:00 |

### 自動化覆蓋率

```
✅ 全自動運作 .................... 7 個區塊
⚠️ 半自動（events 文字手動補） ... 1 個區塊（主時程表 + 今年解盲共用同一資料）
```

### 「⭐ 本週值得注意」與「🎯 AI 動態訊號評估引擎」的差別

| 區塊 | 篩選邏輯 | 主要目的 |
|---|---|---|
| ⭐ 本週值得注意 | `highlightThisWeek:true` 由 `update_highlights.py` 自動標記（新聞觸發） | 即時關注「本週有動靜」的公司 |
| 🎯 AI 動態訊號評分 | 7 模組評分 + 5 風險閘 由 `update_scores.py` 整合計算 | 長期排序與分級（≥80 / ≥65 / 觀察） |

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

### 🎯 情境 A：加入一家新公司（⚠️ 必看 SOP）

**重要**：加入新公司後，**必須立即手動跑 3 個腳本**把它補進 4 個獨立表格，否則使用者要等下次排程（最多 6 天）才會看到。

#### Step 1：編輯 `date.json`
在對應 section（上市/上櫃/興櫃）的 `companies` 陣列加入新物件：
- 必填：`code`, `name`, `market` (listed/otc/emerging), `events` (即使每季都 null 也要有 q1~q4 + h2)
- 建議填：`website`, `strategy`, `indication`, `target`

#### Step 2：立即跑 3 個腳本補進 4 個表格

```bash
# 1. 補現金流（💰 26 家現金流餘額排行）
python update_cashflow.py

# 2. 補千張大戶（🏦 集保戶持股統計 + 🏆 26 家總股東排行）
python update_holders.py

# 3. 算評分（🎯 AI 自動化動態訊號評估引擎）
python update_scores.py

# 4. （選擇性）抓即時股價
python update_prices.py
```

#### Step 3：commit + push

```bash
git add date.json cashflow.json holders.json holders_history.json scores.json status.json
git commit -m "新增 XXXX 第 N 家"
git push origin main
```

#### 為什麼這 4 個表格必須手動補？

| 表格 | 資料源 JSON | 為何要立即跑？ |
|---|---|---|
| 🎯 AI 動態訊號評估引擎 | `scores.json` | 評分需要 cashflow + holders 才能算，3 個都要先有 |
| 🏦 集保戶持股統計 | `holders_history.json` | TDCC 抓取需要爬蟲 |
| 🏆 26 家總股東排行 | `holders_history.json` | 同上 |
| 💰 26 家現金流餘額排行 | `cashflow.json` | FinMind API 呼叫 |

**不跑會怎樣？**
- 新公司在這 4 個表格會「不見」或顯示空欄位
- 動態評分裡看不到
- 集保戶統計顯示 0 持有者
- 排行表會少一家
- 現金流會顯示 ﹣

**會自動補齊嗎？**
是，但要等到：
- 下次平日 06:00/15:00 → `update_prices.py` 自動補股價
- 下次每天 06:00 → 自動補新聞 + 評分
- 下次週六 10:00 → 自動補千張 + 現金流

**所以新加入公司一定要手動觸發**，否則使用者最久要等 6 天（下個週六）才看到完整資料。

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
    - cron: '0 22 * * 0-4'   # 平日 06:00 TST → 早盤股價
    - cron: '0 7 * * 1-5'   # 平日 15:00 TST → 收盤股價
    - cron: '0 22 * * *'     # 每天 06:00 TST → 新聞 + highlights + scores
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
| 改／重建 3D 分子結構圖 | `index.html`（`_MOL3D_CFG`）＋ `spin/*.pdb.gz`；重建方法見第十四節 |
| 改自動化排程時間 | `.github/workflows/update-prices.yml` |
| 看資料抓取的歷史問題 | `DATA_SEARCH_MEMO.md` |
| 看評分引擎邏輯 | `SCORING_ENGINE.md` 或 `update_scores.py` |

---

## 十四、深度分析卡與 3D 分子結構系統

> 頁面在「28 家新聞」上方有幾張可展開的 **深度分析展示卡**（`.pe-showcase` / `<details class="csec">`），
> 全部純寫在 `index.html`（HTML + 內嵌 SVG + JS），資料**非**來自 JSON 排程、也不受 cron 影響。

### 展示卡一覽

| 卡片 | 代號 | 主題 | 特色內容 |
|---|---|---|---|
| 🏆 台灣生技界股王 藥華藥 | 6446 | 成功範例① | 藥物機轉、蛋白序列、他國藥證時程 |
| 🏆 成功範例 仁新醫藥 | 6696 | 成功範例② | Tinlarebant（RBP4）、2D 小分子結構 + SMILES |
| 🌱 台灣醫美潛力生技股 鼎晉生技 | 7876 | 潛力範例 | OBI-858 肉毒桿菌毒素、760 kDa 複合體、**3D 結構** |

### 3D 分子結構檢視器

| 項目 | 實作 |
|---|---|
| **函式庫** | [3Dmol.js](https://3dmol.csb.pitt.edu/) 2.4.2，CDN 載入 |
| **載入時機** | 卡片 `<details>` 首次 `toggle` 展開時才 lazy-load（省流量） |
| **設定物件** | `_MOL3D_CFG[id] = {gz, rot, style}`：資料檔、初始旋轉、著色函式 |
| **資料解壓** | 檔案為 gzip，瀏覽器端用 `DecompressionStream('gzip')` 即時解壓成 PDB 文字 |
| **poster fallback** | 每個 viewer 有靜態 `<img>` 底圖；3Dmol 載入失敗時退回顯示 |

目前鼎晉卡有 **兩顆可對照的 14 鏈 3D**：

| viewer id | 資料檔 | 來源 | 上色 |
|---|---|---|---|
| `mol3d` | `spin/9qcm.pdb.gz` | **實驗結構** RCSB PDB 9QCM（2.9 Å 冷凍電鏡，B1 型，實測 757.93 kDa） | 依鏈（紅/青/粉） |
| `mol3d2` | `spin/af_complex.pdb.gz` | **AlphaFold 組裝模型**（見下） | 依鏈（同上，可直接對照） |

### ★ AlphaFold 14 鏈複合體組裝方法（可重現）

A 型 OBI-858 的完整 L-PTC 尚無實驗結構，故以「AlphaFold 單鏈預測 ＋ 剛體疊合」組裝：

1. **取 5 種蛋白的 AlphaFold 單鏈模型**（UniProt accession → AlphaFold DB）：

   | 鏈 | 蛋白 | UniProt | 份數 |
   |---|---|---|---|
   | A | BoNT/A 神經毒素 | P0DPI1 | ×1 |
   | B | NTNH | A5HZZ8 | ×1 |
   | C–E | HA70 | A5HZZ4 | ×3 |
   | F–H | HA17 | A5HZZ5 | ×3 |
   | I–N | HA33 | A5HZZ6 | ×6 |
   | | | | **合計 14 鏈** |

2. **依 1:1:3:3:6 化學計量** 複製各單鏈為 14 條鏈（A–N）。
3. **Kabsch 剛體疊合**：把每條 AlphaFold 單鏈的 Cα，位置對位疊到實驗模板 **9QCM** 對應鏈的座標上，再把該旋轉平移套用到整條鏈全部原子。
4. 輸出 `spin/af_complex.pdb.gz`（**53,412 原子**），並以自寫 space-filling 渲染器產靜態海報 `bont_af_3d.jpg`（依鏈上色，與實驗圖同配色便於對照）。

- **重建腳本**：`assemble_af14.py`（＋ `render_ptc.py` 渲染海報）保存在開發者 scratchpad，**未進 repo**；上述 4 步已足以重現。
- **誠實標註**：A 型完整複合體無實驗結構 → 空間排列採用同架構（1:1:3:3:6）的 B1 型 9QCM 為模板 → 圖說標明為「**組裝模型**」而非單一實驗解析。
- **授權**：AlphaFold DB 模型 CC BY 4.0（Jumper *Nature* 2021、Varadi *NAR* 2024）；PDB 9QCM 公開。

### 版權原則（重要）

> **不複製期刊 / 廠商的圖檔**。所有結構圖一律以 **公開座標（PDB／AlphaFold DB）或公開序列（UniProt／專利 SEQ ID）自行渲染重製**，並在圖說標註原始來源。
> 760 kDa 交叉驗證三方一致：OBIGEN 公開圖（150+140+470）× 專利 TW202138002A 質量加總 × PDB 9QCM 實測 757.93 kDa。

---

## 十五、聯絡與授權

- 維護者：rebiocadd
- 授權：本專案僅供研究與追蹤參考，不構成投資建議
- 線上版每天自動更新，無需手動 deploy
