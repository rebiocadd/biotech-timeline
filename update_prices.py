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


# ── 雙來源驗證 ────────────────────────────────────────────────
def get_price_verified(code, market, name):
    """
    取得股價並雙來源交叉驗證。
    回傳：(price_str, change_str)  或  (None, None)
    """
    src_name = "TWSE" if market == "listed" else "TPEX"

    p1, chg = fetch_official(code, market)
    p2      = fetch_wantgoo(code)

    status = ""

    if p1 is not None and p2 is not None:
        diff = abs(p1 - p2) / p1 * 100
        if diff > WARN_THRESHOLD:
            status = (f"⚠️  差異 {diff:.1f}%  "
                      f"{src_name}={p1:.2f}  玩股網={p2:.2f}  → 採用{src_name}")
        else:
            status = f"✅  {p1:.2f} ({chg:+.2f}%)  雙源一致 Δ{diff:.1f}%"
        final_price, final_chg = p1, chg

    elif p1 is not None:
        status = f"⚠️  {p1:.2f} ({chg:+.2f}%)  僅{src_name}（玩股網失敗）"
        final_price, final_chg = p1, chg

    elif p2 is not None:
        status = f"⚠️  {p2:.2f}  僅玩股網（{src_name}失敗，無漲跌%）"
        final_price, final_chg = p2, 0.0

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

    if fail_list:
        sys.exit(1)


if __name__ == "__main__":
    main()
