#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_prices.py
雙來源股價驗證更新腳本
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
來源1（主）：TWSE / TPEX 官方 API（JSON，最可靠）
來源2（驗）：玩股網 wantgoo.com（HTML解析，交叉確認）

差異超過 WARN_THRESHOLD % 時顯示警告並採用官方數據。

用法：
  python update_prices.py          # 更新今日股價
  python update_prices.py --push   # 更新後自動 git commit & push
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json, re, time, sys, os, subprocess
import urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

# ── 設定 ──────────────────────────────────────────────────────
JSON_PATH    = os.path.join(os.path.dirname(__file__), "date.json")
WARN_THRESHOLD = 3.0          # 雙來源差異超過此 % 才警告
REQUEST_DELAY  = 0.8          # 每次請求間隔（秒），避免被封鎖
TAIPEI_TZ      = timezone(timedelta(hours=8))   # UTC+8

now       = datetime.now(TAIPEI_TZ)
ROC_DATE  = f"{now.year - 1911}/{now.month:02d}/{now.day:02d}"
TODAY_STR = f"{now.month:02d}/{now.day:02d}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "zh-TW,zh;q=0.9",
}

# ── 來源0：Yahoo Finance（穩定備援，全球可用）─────────────────
def fetch_yahoo(code):
    """從 Yahoo Finance 取收盤價（自動嘗試 .TW 和 .TWO 後綴）"""
    for suffix in ('.TW', '.TWO'):
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{code}{suffix}?interval=1d&range=5d"
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=12) as r:
                data = json.loads(r.read().decode("utf-8"))
            result = (data.get("chart", {}) or {}).get("result") or []
            if not result:
                continue
            quote = result[0].get("indicators", {}).get("quote", [{}])[0]
            closes = [c for c in (quote.get("close") or []) if c is not None]
            if not closes:
                continue
            close = float(closes[-1])
            prev  = float(closes[-2]) if len(closes) >= 2 else close
            chg   = round((close - prev) / prev * 100, 2) if prev else 0.0
            return close, chg
        except Exception:
            continue
    return None, None


# ── 來源1：TWSE / TPEX 官方 API ───────────────────────────────
def fetch_official(code, market):
    """
    上市 → TWSE STOCK_DAY API（月資料，取最後一筆收盤）
    上櫃/興櫃 → TPEX 個股日成交 API
    回傳：(收盤價, 漲跌%)  或  (None, None)
    """
    try:
        if market == "listed":
            url = (f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
                   f"?stockNo={code}&response=json")
        else:
            url = (f"https://www.tpex.org.tw/web/stock/aftertrading/"
                   f"daily_trading_info/st43_result.php"
                   f"?l=zh-tw&d={ROC_DATE}&stkno={code}")

        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read().decode("utf-8"))

        rows = data.get("data") or data.get("aaData") or []
        if not rows:
            return None, None

        def parse_price(s):
            return float(str(s).replace(",", "").strip())

        close = parse_price(rows[-1][6])
        prev  = parse_price(rows[-2][6]) if len(rows) >= 2 else close
        chg   = round((close - prev) / prev * 100, 2) if prev else 0.0
        return close, chg

    except Exception as e:
        return None, None


# ── 來源2：玩股網 wantgoo.com ────────────────────────────────
def fetch_wantgoo(code):
    """
    從玩股網頁面解析收盤價（多重 regex 備援）
    回傳：收盤價  或  None
    """
    try:
        url = f"https://www.wantgoo.com/stock/{code}"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12) as r:
            html = r.read().decode("utf-8")

        patterns = [
            r'"regularMarketPrice"\s*:\s*([\d.]+)',
            r'"close"\s*:\s*([\d.]+)',
            r'id="close_price"[^>]*>\s*([\d,]+\.?\d*)',
            r'class="[^"]*close[^"]*price[^"]*"[^>]*>\s*([\d,]+\.?\d*)',
            r'收盤[價价]\D{0,15}([\d,]+\.?\d+)',
        ]
        for pat in patterns:
            m = re.search(pat, html)
            if m:
                price = float(m.group(1).replace(",", ""))
                if 1.0 < price < 999999:   # 合理股價範圍
                    return price
    except Exception:
        pass
    return None


# ── 三來源驗證 ────────────────────────────────────────────────
def get_price_verified(code, market, name):
    """
    取得股價並三來源驗證（Yahoo + TWSE/TPEX + 玩股網）。
    優先順序：1) Yahoo（最穩定）  2) TWSE/TPEX  3) 玩股網
    若有 2 個以上來源成功則交叉驗證。
    回傳：(price, change)  或  (None, None)
    """
    src_name = "TWSE" if market == "listed" else "TPEX"

    # 三個來源都試
    p_yahoo, chg_yahoo = fetch_yahoo(code)
    p_official, chg_official = fetch_official(code, market)
    p_wantgoo = fetch_wantgoo(code)

    # 收集成功的來源
    sources = []
    if p_yahoo is not None:    sources.append(("Yahoo", p_yahoo, chg_yahoo))
    if p_official is not None: sources.append((src_name, p_official, chg_official))
    if p_wantgoo is not None:  sources.append(("玩股網", p_wantgoo, None))

    status = ""

    if len(sources) >= 2:
        # 多來源交叉驗證
        prices = [s[1] for s in sources]
        max_diff = (max(prices) - min(prices)) / min(prices) * 100
        # 優先採用有漲跌%的（Yahoo 或 TWSE/TPEX）
        primary = next((s for s in sources if s[2] is not None), sources[0])
        if max_diff > WARN_THRESHOLD:
            status = f"⚠️  {primary[1]:.2f} 多源差異 {max_diff:.1f}% → 採用 {primary[0]}"
        else:
            srcs = "/".join(s[0] for s in sources)
            status = f"✅  {primary[1]:.2f} ({primary[2]:+.2f}%) {srcs} 一致"
        final_price = primary[1]
        final_chg   = primary[2] if primary[2] is not None else 0.0

    elif len(sources) == 1:
        s = sources[0]
        status = f"⚠️  {s[1]:.2f} 僅 {s[0]} 成功"
        final_price = s[1]
        final_chg   = s[2] if s[2] is not None else 0.0

    else:
        status = "❌  所有來源失敗"
        final_price, final_chg = None, None

    print(f"  [{code}] {name:<10}  {status}")
    return final_price, final_chg


# ── 主程式 ────────────────────────────────────────────────────
def main():
    auto_push = "--push" in sys.argv

    print("=" * 55)
    print(f" 台灣生技股 股價更新腳本")
    print(f" 日期：{now.strftime('%Y/%m/%d')}  民國：{ROC_DATE}")
    print(f" 雙來源：TWSE/TPEX 官方API + 玩股網（差異>{WARN_THRESHOLD}%警告）")
    print("=" * 55)

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    ok_count, fail_list = 0, []

    for section in data:
        print(f"\n── {section['section']} ──")
        for company in section["companies"]:
            code   = company["code"]
            market = company["market"]
            name   = company["name"]

            price, chg = get_price_verified(code, market, name)
            time.sleep(REQUEST_DELAY)

            if price is not None:
                company["price"]     = f"{price:.2f}"
                company["change"]    = f"{chg:+.2f}" if chg >= 0 else f"{chg:.2f}"
                company["priceDate"] = TODAY_STR
                ok_count += 1
            else:
                fail_list.append(f"{name}({code})")

    # 寫回 JSON
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    # 更新狀態
    try:
        from _status_helper import update_status
        update_status("prices")
    except Exception as e:
        print(f"⚠️ 狀態更新失敗：{e}")

    print("\n" + "=" * 55)
    print(f" ✅ 成功更新：{ok_count} 家公司")
    if fail_list:
        print(f" ❌ 失敗：{', '.join(fail_list)}")
    print(f" 📁 已寫入 {JSON_PATH}")
    print("=" * 55)

    # 自動 push
    if auto_push:
        print("\n🚀 自動 git commit & push...")
        os.chdir(os.path.dirname(__file__))
        subprocess.run(["git", "add", "date.json"], check=True)
        msg = f"更新股價 {now.strftime('%Y/%m/%d')}"
        subprocess.run(["git", "commit", "-m", msg], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("✅ 已推送至 GitHub")
    else:
        print("\n👉 下一步：git add date.json && git commit -m '更新股價' && git push")

    # 即使部分失敗，只要有任何成功就視為 OK（避免整個 GitHub Actions step 失敗）
    if fail_list and ok_count == 0:
        print("\n❌ 全部失敗，視為錯誤")
        sys.exit(1)
    elif fail_list:
        print(f"\n⚠️ 部分成功（{ok_count} 成功 / {len(fail_list)} 失敗），失敗的公司保留原資料")


if __name__ == "__main__":
    main()
