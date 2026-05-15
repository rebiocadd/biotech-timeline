#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_holders.py - 每週自動更新千張大戶統計
資料來源：TDCC 集保戶股權分散表 (smart.tdcc.com.tw)
執行時機：每週六上午 10:00（TDCC 於週六發布前週最後一日資料）

用法：
  python update_holders.py          # 更新 holders.json
  python update_holders.py --push   # 更新後自動 git commit & push
"""

import json, re, sys, os, subprocess, urllib.request, urllib.error
from datetime import datetime, timedelta

JSON_PATH = os.path.join(os.path.dirname(__file__), "holders.json")
HISTORY_PATH = os.path.join(os.path.dirname(__file__), "holders_history.json")
MAX_WEEKS = 52  # 保留最多一年（52週）的歷史資料

COMPANIES = [
    ("4147","中裕新藥"), ("6919","康霈生技"), ("6535","順藥"),   ("6576","逸達生技"),
    ("4162","智擎生技"), ("6446","藥華藥"),   ("6949","沛爾生醫"),("7878","藥祇生醫"),
    ("7827","漢康生技"), ("6467","泰合生技"), ("6696","仁新醫藥"),("7829","思捷優達"),
    ("6917","竟天生技"), ("6945","圓祥生技"), ("7871","安立璽榮"),("6610","安成生技"),
    ("7876","鼎晉生技"), ("4168","醣聯"),     ("7754","安基生技"),("7902","宇越生醫"),
    ("6709","昱厚生技"), ("7776","奧孟亞"),   ("6492","生華科"),  ("6712","長聖"),
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def get_page_token(session_cookies):
    """GET 頁面取得 CSRF token 和 cookie"""
    import http.cookiejar
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    req = urllib.request.Request("https://www.tdcc.com.tw/portal/zh/smWeb/qryStock", headers=HEADERS)
    html = opener.open(req, timeout=15).read().decode("utf-8", errors="ignore")
    token_m = re.search(r'name="SYNCHRONIZER_TOKEN"\s+value="([^"]+)"', html)
    token = token_m.group(1) if token_m else ""
    return opener, token

def query_stock(opener, token, code, date):
    """查詢個股特定週的千張大戶資料（Level 15：1,000,001股以上）"""
    params = {
        "SYNCHRONIZER_TOKEN": token, "SYNCHRONIZER_URI": "/portal/zh/smWeb/qryStock",
        "method": "submit", "firDate": date, "scaDate": date,
        "sqlMethod": "StockNo", "stockNo": code, "stockName": ""
    }
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        "https://www.tdcc.com.tw/portal/zh/smWeb/qryStock",
        data=data, headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                             "Referer": "https://www.tdcc.com.tw/portal/zh/smWeb/qryStock"}
    )
    html = opener.open(req, timeout=15).read().decode("utf-8", errors="ignore")
    # 解析 Level 15（1,000,001以上）
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        cells = [re.sub(r'<[^>]+>','',c).replace(',','').strip() for c in cells]
        if len(cells) >= 4 and '1,000,001' in row.replace(',','').replace('1000001','1,000,001'):
            try:
                return int(cells[2]), int(cells[3])  # 人數, 股數
            except:
                pass
    return 0, 0

def get_total_shares(opener, token, code, date):
    """取得總發行股數（Level 16 合計行）"""
    params = {
        "SYNCHRONIZER_TOKEN": token, "SYNCHRONIZER_URI": "/portal/zh/smWeb/qryStock",
        "method": "submit", "firDate": date, "scaDate": date,
        "sqlMethod": "StockNo", "stockNo": code, "stockName": ""
    }
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        "https://www.tdcc.com.tw/portal/zh/smWeb/qryStock",
        data=data, headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded",
                             "Referer": "https://www.tdcc.com.tw/portal/zh/smWeb/qryStock"}
    )
    html = opener.open(req, timeout=15).read().decode("utf-8", errors="ignore")
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        cells = [re.sub(r'<[^>]+>','',c).replace(',','').strip() for c in cells]
        if len(cells) >= 4 and '計' in row:
            try: return int(cells[3])
            except: pass
    return 0

def get_available_dates(opener, token):
    """取得 TDCC 可用的日期列表（最近兩週）"""
    req = urllib.request.Request("https://www.tdcc.com.tw/portal/zh/smWeb/qryStock", headers=HEADERS)
    html = opener.open(req, timeout=15).read().decode("utf-8", errors="ignore")
    dates = re.findall(r'<option value="(\d{8})"', html)
    return sorted(set(dates), reverse=True)[:2]  # 最近兩週

def main():
    import urllib.parse
    auto_push = "--push" in sys.argv
    now = datetime.now()

    print("=" * 55)
    print(" 千張大戶週統計更新腳本")
    print(f" 執行時間：{now.strftime('%Y/%m/%d %H:%M')}")
    print("=" * 55)

    # 取得 session
    print("\n取得 TDCC session...")
    opener, token = get_page_token({})
    dates = get_available_dates(opener, token)
    if len(dates) < 2:
        print("❌ 無法取得兩週日期，請稍後再試")
        sys.exit(1)

    curr_date_raw, prev_date_raw = dates[0], dates[1]
    curr_date = f"{curr_date_raw[4:6]}/{curr_date_raw[6:]}"
    prev_date = f"{prev_date_raw[4:6]}/{prev_date_raw[6:]}"
    print(f"本週日期：{curr_date}（{curr_date_raw}）")
    print(f"上週日期：{prev_date}（{prev_date_raw}）")

    # 讀取現有資料（保留 total_s）
    existing = {}
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            old = json.load(f)
        for r in old.get("data", []):
            existing[r["code"]] = r.get("total_s", 0)

    results = []
    ok, fail = 0, []

    for code, name in COMPANIES:
        print(f"\n  [{code}] {name}...", end=" ", flush=True)
        try:
            # 重新取 token（每次查詢需要新 token）
            opener2, token2 = get_page_token({})
            curr_h, curr_s = query_stock(opener2, token2, code, curr_date_raw)

            opener3, token3 = get_page_token({})
            prev_h, prev_s = query_stock(opener3, token3, code, prev_date_raw)

            total_s = existing.get(code, 0)
            if total_s == 0:
                opener4, token4 = get_page_token({})
                total_s = get_total_shares(opener4, token4, code, curr_date_raw)

            results.append({
                "code": code, "name": name,
                "curr_h": curr_h, "curr_s": curr_s,
                "prev_h": prev_h, "prev_s": prev_s,
                "total_s": total_s
            })
            dh = curr_h - prev_h
            ds = curr_s - prev_s
            dh_str = f"+{dh}" if dh > 0 else str(dh) if dh < 0 else "="
            ds_str = f"+{ds:,}" if ds > 0 else f"{ds:,}" if ds < 0 else "="
            print(f"人數{dh_str} 持股{ds_str}")
            ok += 1
        except Exception as e:
            print(f"❌ {e}")
            fail.append(f"{name}({code})")

    # 寫入舊格式 holders.json（向後相容）
    output = {"curr_date": curr_date, "prev_date": prev_date, "data": results}
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

    # 更新歷史檔 holders_history.json：將本週 snapshot 加入歷史前端
    history = {"weeks": []}
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = {"weeks": []}

    # 本週 snapshot
    new_snapshot = {
        "date": curr_date,
        "rawDate": curr_date_raw,
        "data": [
            {"code": r["code"], "name": r["name"],
             "h": r["curr_h"], "s": r["curr_s"], "total_s": r["total_s"]}
            for r in results
        ],
    }

    # 移除同日期的舊紀錄（若已存在），再插入到最前
    weeks = [w for w in history.get("weeks", []) if w.get("date") != curr_date]
    weeks.insert(0, new_snapshot)
    history["weeks"] = weeks[:MAX_WEEKS]  # 限制歷史長度

    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, separators=(",", ":"))

    print(f"\n{'='*55}")
    print(f" ✅ 成功：{ok}/{len(COMPANIES)} 家")
    if fail: print(f" ❌ 失敗：{', '.join(fail)}")
    print(f" 📁 holders.json 已更新")
    print(f" 📚 holders_history.json 共 {len(history['weeks'])} 週歷史")
    print("=" * 55)

    if auto_push:
        print("\n🚀 自動 git commit & push...")
        os.chdir(os.path.dirname(__file__))
        subprocess.run(["git", "add", "holders.json"], check=True)
        msg = f"自動更新千張大戶統計 {now.strftime('%Y/%m/%d')}"
        try:
            subprocess.run(["git", "commit", "-m", msg], check=True)
            subprocess.run(["git", "push", "origin", "main"], check=True)
            print("✅ 已推送至 GitHub")
        except subprocess.CalledProcessError:
            print("⚠️ 無變更或推送失敗")

if __name__ == "__main__":
    main()
