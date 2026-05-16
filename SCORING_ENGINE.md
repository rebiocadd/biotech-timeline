# 🎯 動態投資評分引擎 · Dynamic Investment Scoring Engine

> **不是投資建議**，僅供研究與風險排序工具

---

## 📦 檔案結構

```
biotech-timeline/
├── config/
│   └── scoringWeights.json     # 所有權重與門檻（集中管理）
├── update_scores.py             # 後端評分引擎（Python）
├── scores.json                  # 計算結果 + 90 天歷史
├── index.html                   # 前端 dashboard（已嵌入）
└── SCORING_ENGINE.md            # 本文件
```

---

## 🧮 7 個評分模組（每個 0–100）

| 模組 | 權重 | 看什麼 |
|------|:---:|------|
| **CatalystScore** | 25% | 事件類型、距離天數、臨床期別、狀態 |
| **CashRunwayScore** | 20% | 現金部位 / 月燒錢 = 剩餘月份 |
| **PricePositionScore** | 15% | 距離 240 日高點、20 日漲幅 |
| **TrendScore** | 10% | MA60/120/240 排列、量能 |
| **ShareholderScore** | 10% | 千張大戶 + 總股東變化 |
| **NewsSentimentScore** | 10% | 催化新聞數、負面新聞、近期密度 |
| **ClinicalCredibilityScore** | 10% | 臨床期別、延遲、合作夥伴、孤兒藥/BTD |

**總分公式**：
```
InvestmentScore = 0.25*Catalyst + 0.20*CashRunway + 0.15*PricePosition
                + 0.10*Trend + 0.10*Shareholder + 0.10*NewsSentiment
                + 0.10*ClinicalCredibility
```

---

## 🎨 分數區段

| 區間 | 標籤 | 顏色 |
|------|------|------|
| 80–100 | 🟢 高度研究名單 | green |
| 65–79  | 🔵 可觀察進場 | cyan |
| 50–64  | 🟡 觀察 | yellow |
| 35–49  | 🟠 風險升高 | orange |
| 0–34   | 🔴 暫不考慮 | red |

---

## ⚠️ 風險閘門（不論總分多高都會疊加標籤）

| 條件 | 標籤 | 嚴重度 |
|------|------|:---:|
| Cash runway < 12 個月 | 高增資風險 | high |
| 20 日漲幅 > 40% 且無正式公告 | 短線過熱 | medium |
| 催化事件 > 180 天 + 股價已漲 > 60% | 催化太遠股價已超前 | medium |
| 臨床事件延遲 ≥ 2 次 | 臨床可信度下降 | medium |
| 年增股本稀釋率 > 15% | 股本稀釋風險 | high |

---

## 📊 資料來源對應

| 評分模組 | 讀取檔案 | 欄位 |
|----------|---------|------|
| Catalyst | `date.json` | events.q?.tag/label/statusLabel/highlightThisWeek |
| CashRunway | `cashflow.json` | cash_2025/2026, cf_2025/2026 |
| PricePosition | `date.json` | priceHistory[].close |
| Trend | `date.json` | priceHistory (MA 算法) |
| Shareholder | `holders.json` | curr_h/prev_h/total_h/prev_total_h |
| NewsSentiment | `news_status.json` | companies[code].news[].title |
| ClinicalCredibility | `date.json` | events 的 label/drug + 全文 keywords |

---

## ⏰ 自動化

GitHub Actions cron（`.github/workflows/update-prices.yml` 的 `update-news` job）每日 08:00 (UTC+8)：

```
1. update_news.py        ← 抓 Google News
2. update_highlights.py  ← 自動標記本週重點
3. update_scores.py      ← ★ 計算 25 家 InvestmentScore
4. git commit + push
```

每次運行：
- 即時計算所有 7 個分數
- 保留歷史（每日一筆，最多 90 天）
- 寫入 `scores.json`
- 前端自動讀取顯示

---

## 🛠️ 調整權重（不用改程式）

編輯 `config/scoringWeights.json`：

```json
{
  "totalWeights": {
    "catalyst":         0.25,    ← 想加重催化？改成 0.30
    "cashRunway":       0.20,
    "pricePosition":    0.15,
    ...
  },
  "catalyst": {
    "eventTypeWeights": {
      "tag-approval":   100,     ← 藥證權重
      "tag-resolve":     95,     ← 解盲權重
      ...
    },
    ...
  }
}
```

下次 `update_scores.py` 跑時即套用。**所有門檻、係數、加權都在這個 JSON**。

---

## 📈 前端 Dashboard（`index.html`）

位置：在「⭐ 本週值得注意」上方。

### 顯示內容
- 每家公司一張卡片：
  - 公司名 + 代號
  - 總分（大字 18px）+ 區段標籤
  - 7 個分項分數的橫條
  - 風險標籤
- 上方過濾標籤：全部 / ≥80 / ≥65 / 高增資風險 / 短線過熱

### 過濾與排序
- 卡片永遠依總分由高到低排序
- 點過濾標籤切換顯示範圍

---

## 🧪 手動執行

```bash
cd D:\AI-agent\AI-claude\BioStock\biotech-timeline
python update_scores.py
```

執行後：
1. 印出每家公司分數明細
2. Top 10 排行
3. 寫入 `scores.json`
4. 更新 `status.json` 加入 `scores.lastRun`

---

## 📂 scores.json 結構

```json
{
  "lastRun": "2026/05/16 23:17",
  "tz": "UTC+8",
  "weightsVersion": "1.0",
  "companies": {
    "6446": {
      "code": "6446",
      "name": "藥華藥",
      "total": 82.5,
      "band": {"min":80,"max":100,"label":"高度研究名單","color":"#10b981"},
      "components": {
        "catalyst": 100,
        "cashRunway": 100,
        "pricePosition": 55,
        "trend": 75,
        "shareholder": 75,
        "newsSentiment": 80,
        "clinicalCredibility": 95
      },
      "metadata": {
        "cash_runway_months": null,
        "cash": 22693000000,
        "gain_20d": 10.7,
        "news_count": 5,
        "shareholder_change": -492
      },
      "riskFlags": []
    },
    ...
  },
  "history": {
    "6446": [
      {"date":"2026-05-15","total":81.2,"components":{...},"band_label":"高度研究名單"},
      {"date":"2026-05-16","total":82.5,"components":{...},"band_label":"高度研究名單"}
    ]
  }
}
```

歷史最多保留 **90 天**，前端可繪製趨勢圖（待開發）。

---

## 🚧 待擴充功能（後續）

- [ ] 雷達圖 (radar chart) 取代橫條
- [ ] 分數歷史折線圖
- [ ] 本週分數變化 Top 10（升幅最大）
- [ ] 240 日股價歷史擴充（目前只 5 日）
- [ ] 臨床事件延遲追蹤（需歷史比對）
- [ ] 月平均燒錢速度精確化（目前用年化 OCF/12）

---

## ⚠️ 重要聲明

1. 本工具**不是投資建議**
2. 評分模型基於公開資訊與經驗權重，**不保證準確**
3. 生技股波動極大，**請自行評估風險**
4. 「高度研究名單」不等於「應該買進」
5. 風險閘門是**警示**，不是禁止

請依個人風險承受度與專業判斷做投資決定。
