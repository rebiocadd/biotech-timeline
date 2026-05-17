# 台股財務資料徹底追查 SOP

> 建立日期：2026-05-17
> 目的：記錄「藥華藥 2026 Q1 現金」追查過程，作為日後追新資料源的範本

---

## TL;DR（一頁結論）

1. **上市/上櫃公司 Q1**：用 **FinMind API** 是最快、最完整的免費來源（覆蓋率 100%）
2. **興櫃公司 Q1**：**法規上不存在**，興櫃只需揭露年報+半年報，別白費力氣
3. **yfinance** 永遠延遲 1-2 季，不要當主來源
4. **MOPS / Goodinfo** 反爬蟲嚴重，requests + UA 偽裝沒用，需 Chrome 真實瀏覽器
5. **TWSE OpenAPI** 只有損益表沒有資產負債表的現金欄位

---

## 個股 Q1 現金追查的標準流程（SOP）

### Step 1：先確認該公司的市場類型

不同市場揭露義務不同：

| 市場 | 簡稱 | Q1 季報義務 | 截止日 |
|---|---|---|---|
| 上市 | TWSE (sii) | 必須 | 5/15 |
| 上櫃 | TPEx (otc) | 必須 | 5/15 |
| **興櫃** | **Emerging** | **不需要** | （只交年報+半年報） |

#### 用 OpenAPI 快速分類

```python
# 上市公司清單
url = 'https://openapi.twse.com.tw/v1/opendata/t187ap03_L'
# 上櫃公司清單
url = 'https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O'
```

不在這兩個清單裡的，就是興櫃。

---

### Step 2：依市場類型選資料源

```
        ┌─ 上市 ──→ FinMind (TaiwanStockBalanceSheet) ── 100% 覆蓋
        │
        ├─ 上櫃 ──→ FinMind (同上) ── 多數有
        │
        └─ 興櫃 ──→ Q1 不存在，最多到 Q4 年報
                    └─→ 若硬要找：Goodinfo 季報（部分公司自願揭露）
```

---

### Step 3：FinMind API 用法

```python
import urllib.request, urllib.parse, json

url = 'https://api.finmindtrade.com/api/v4/data'
params = {
    'dataset': 'TaiwanStockBalanceSheet',
    'data_id': '6446',           # 股票代號
    'start_date': '2023-01-01',
    'end_date': '2026-12-31',
}
full = url + '?' + urllib.parse.urlencode(params)
req = urllib.request.Request(full, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=20) as r:
    data = json.loads(r.read().decode('utf-8'))

# data['data'] 是 list of dict
# 每筆 = {date, stock_id, type, value, origin_name}
# type='CashAndCashEquivalents' → 現金及約當現金
```

**重要 type 對照**：

| FinMind type | 中文 origin_name |
|---|---|
| `CashAndCashEquivalents` | 現金及約當現金（最常用） |
| `CashCashEquivalentsAndShortTermInvestments` | 現金 + 短期投資 |
| `FinancialAssetsAtAmortizedCost` | 按攤銷後成本衡量之金融資產－流動 |

**配額**：免費版 5,000 requests/day，26 家 × 1 call 完全夠用。

---

### Step 4：FinMind 找不到時的 fallback 順序

#### A. yfinance（穩定，但延遲 1-2 季）

```python
import yfinance as yf
t = yf.Ticker('6446.TW')   # 上市
t = yf.Ticker('6446.TWO')  # 上櫃/興櫃
qbs = t.quarterly_balance_sheet
# 注意：通常只到 2-3 個月前
```

#### B. Goodinfo（需瀏覽器，requests 會被擋）

URL pattern：
```
https://goodinfo.tw/tw/StockFinDetail.asp?RPT_CAT=BS_M_QUAR&STOCK_ID={code}
```

只能用 Chrome MCP 真實瀏覽器抓，普通 urllib + UA 拿到的會是 1131 bytes 空頁。

#### C. MOPS 公開資訊觀測站（反爬最嚴）

```
https://mops.twse.com.tw/mops/web/ajax_t164sb03
POST: co_id=6446&year=115&season=01
```

直接 POST 會回「THE PAGE CANNOT BE ACCESSED」。要先 GET 首頁拿 cookie + session，但通常也被擋。建議跳過，用 Chrome MCP。

#### D. TWSE OpenAPI（只有損益表，沒有現金）

```
https://openapi.twse.com.tw/v1/opendata/t187ap14_L
```

可確認 Q1 報告**是否已出表**（有「出表日期」欄位），但無資產負債表細項。
用途：確認某公司今年 Q1 報告是否已申報，作為「該找了」的訊號。

---

## 已驗證的 endpoint 對照表

| 來源 | URL / endpoint | 認證 | 配額 | 涵蓋季度 | 結論 |
|---|---|---|---|---|---|
| **FinMind** | `api.finmindtrade.com/api/v4/data` | 免費（可註冊取 token 提額） | 5000/day | 到上一季 | ⭐⭐⭐⭐⭐ 主來源 |
| **yfinance** | python lib | 無 | 無限 | 通常落後 1-2 季 | ⭐⭐⭐ 備援 |
| **TWSE OpenAPI** | `openapi.twse.com.tw/v1/opendata/t187ap14_L` | 無 | 無限 | 季報出表狀態 | ⭐⭐ 確認出表用 |
| **Goodinfo** | `goodinfo.tw/tw/StockFinDetail.asp` | 無 | 反爬限制 | 全季 | ⭐⭐ 需 Chrome MCP |
| **MOPS** | `mops.twse.com.tw/mops/web/ajax_*` | session cookie | 強反爬 | 全季 | ⭐ 不建議用 requests |
| **Yahoo TW** | `tw.stock.yahoo.com/quote/{code}.TW/balance-sheet` | 無 | 無限 | 有 2026 但需 JS render | ⭐⭐ 需 Playwright |
| **cnyes** | `www.cnyes.com/twstock/financial/...` | 無 | 動態 SPA | 需 JS render | ⭐ 不建議 |
| **wantgoo** | `www.wantgoo.com/stock/{code}/...` | 無 | 動態 SPA | 需 JS render | ⭐ 同上 |

---

## 實戰案例：藥華藥 (6446) 2026 Q1 現金追查

### 時間：2026-05-17（當天就是 Q1 申報截止日 +2）

| 嘗試順序 | 來源 | 結果 | 耗時 |
|---|---|---|---|
| 1 | yfinance quarterly_balance_sheet | 只到 2025-12-31 | 5s |
| 2 | Goodinfo BS_M_QUAR | 被擋（1131 bytes 空頁） | 3s |
| 3 | MOPS ajax_t164sb03 | "PAGE CANNOT BE ACCESSED" | 3s |
| 4 | Yahoo TW balance-sheet 頁 | 有 2026 但需 JS render | 5s |
| 5 | TWSE OpenAPI t187ap14_L | ✅ 確認 2026 Q1 報告已出表，但只有損益表 | 4s |
| 6 | **FinMind TaiwanStockBalanceSheet** | ✅ **找到 24,175,410,000 元 = 241.75 億** | 4s |

**總耗時：約 30 秒**。下次直接從 FinMind 開始，5 秒搞定。

---

## 自動化整合策略

`update_cashflow.py` 的優先順序：

```
1. FinMind (主)
   ├─ 4 年現金 (2023/2024/2025/2026)
   └─ 對上市/上櫃 100% 覆蓋

2. yfinance (備)
   └─ 補 operating_cf 營業現金流（FinMind 無此欄位）

3. existing 沿用 (補)
   └─ Goodinfo 手動資料（興櫃公司用）
```

每週六 10:00 TST 自動跑，2026 Q2 釋出後（約 8/14 前）會自動接續。

---

## 興櫃公司現金資料的特殊處理

### 現狀（12 家興櫃）

| 公司 | 最新 FinMind 季度 |
|---|---|
| 藥祇生醫 7878 / 安成生技 6610 / 鼎晉生技 7876 / 安立璽榮 7871 | 2025-12-31 |
| 竟天生技 6917 / 仁新醫藥 6696 / 思捷優達 7829 / 安基生技 7754 | 2025-12-31 |
| 宇越生醫 7902 / 昱厚生技 6709 / 奧孟亞 7776 / 仲恩生醫 7729 | 2025-12-31 |

### 為什麼興櫃沒有 Q1？

依「證券櫃檯買賣中心興櫃股票相關規定」：

| 報告類型 | 上市/上櫃 | 興櫃 |
|---|---|---|
| 年報（Q4） | ✅ 必須 | ✅ 必須 |
| 半年報（H1） | ✅ 必須 | ✅ 必須 |
| 第一季季報（Q1） | ✅ 必須 | ❌ 不需要 |
| 第三季季報（Q3） | ✅ 必須 | ❌ 不需要 |

所以興櫃公司**法律上根本沒有 Q1 申報義務**，找不到不是 bug。

### 何時可能有資料？

1. 公司**自願揭露**（少數做投資人關係的會發新聞稿）
2. 公司**轉上櫃**後（會補申報 Q1）
3. **下半年 9 月**（公司 H1 半年報出來）

### UI 建議顯示

- 興櫃公司 2026 Q1/Q3 欄位顯示 `興櫃·無Q1` 或保留 `—`
- Tooltip 說明：「興櫃公司法規不需揭露 Q1，最新數字為 2025 年底」

---

## 加入新公司時的檢查清單

新增公司到 `date.json` 時，依此清單確認資料源：

- [ ] **股票代號** 4-5 碼
- [ ] **市場類型**：用 TWSE/TPEx OpenAPI 查證（不要相信公司新聞稿說「即將上櫃」）
- [ ] **FinMind 試抓 2023-2026 現金**：`update_cashflow.py` 跑一次
- [ ] **TDCC 千張資料**：`update_holders.py` 看是否有資料
- [ ] **若是興櫃**：預期沒有 Q1 / Q3，標註「興櫃」字樣
- [ ] **若是新轉上市/上櫃**：歷史可能殘缺，需手動補 Goodinfo 1-2 季

---

## 其他常用的 FinMind dataset（備忘）

| dataset | 用途 |
|---|---|
| `TaiwanStockBalanceSheet` | 資產負債表（現金、應收帳款...）|
| `TaiwanStockFinancialStatements` | 綜合損益表（營收、毛利、淨利）|
| `TaiwanStockCashFlowsStatement` | 現金流量表（OCF / ICF / FCF）|
| `TaiwanStockShareholding` | 集保戶股權分散表 |
| `TaiwanStockPER` | 本益比 |
| `TaiwanStockDividend` | 股利政策 |
| `TaiwanStockNews` | 新聞（替代 Google News）|

API 文件：https://finmind.github.io/

---

## 維護注意事項

1. **FinMind 限額**：免費 5000/day。每週六跑 26 家 × 1 call = 26，每天約 28（含其他腳本），完全夠用。若超過可註冊免費 token 提到 6000/hour。
2. **季報時程**：上市/上櫃 Q1 5/15、Q2 8/14、Q3 11/14、年報 3/31。FinMind 通常 1-3 天內收錄。
3. **興櫃公司若轉上櫃**：原本沒 Q1 的會突然出現多季資料，update_cashflow.py 會自動補上。
4. **若 FinMind 服務中斷**：fallback 到 yfinance（會延遲 1-2 季）+ Goodinfo 手動。
