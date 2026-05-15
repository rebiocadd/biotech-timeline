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
from datetime import datetime, timedelta, timezone

# 強制 stdout 用 UTF-8（避開 Windows cp950 無法顯示 emoji）
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

TAIPEI_TZ = timezone(timedelta(hours=8))   # UTC+8

JSON_PATH = os.path.join(os.path.dirname(__file__), "holders.json")
HISTORY_PATH = os.path.join(os.path.dirname(__file__), "holders_history.json")
DATE_PATH = os.path.join(os.path.dirname(__file__), "date.json")
MAX_WEEKS = 52  # 保留最多一年（52週）的歷史資料


def load_companies():
    """自動從 date.json 載入公司清單（上市 + 興櫃合併）
    這樣未來新增公司時，千張大戶範圍會自動同步。
    """
    with open(DATE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    companies = []
    for section in data:
        for c in section["companies"]:
            companies.append((c["code"], c["name"]))
    return companies


COMPANIES = load_companies()

# 15 個持股等級（涵蓋 TDCC 全部 1~15 級）— 從千張到不足一張
# 順序很重要：由大到小排序，搭配 parser 的 break 機制可避免短 marker 誤匹配長 range
LEVEL_DEFS = [
    # (level_key, html_marker_text, display_label)
    ("1000k+",    "1,000,001",  "1,000,001+ 股"),
    ("800-1000k", "800,001",    "800,001-1,000,000"),
    ("600-800k",  "600,001",    "600,001-800,000"),
    ("400-600k",  "400,001",    "400,001-600,000"),
    ("200-400k",  "200,001",    "200,001-400,000"),
    ("100-200k",  "100,001",    "100,001-200,000"),
    ("50-100k",   "50,001",     "50,001-100,000"),
    ("40-50k",    "40,001",     "40,001-50,000"),
    ("30-40k",    "30,001",     "30,001-40,000"),
    ("20-30k",    "20,001",     "20,001-30,000"),
    ("15-20k",    "15,001",     "15,001-20,000"),
    ("10-15k",    "10,001",     "10,001-15,000"),
    ("5-10k",     "5,001",      "5,001-10,000"),
    ("1-5k",      "1,000-",     "1,000-5,000"),     # marker 含「-」避免誤匹配 1,000,xxx
    ("0-999",     "1-999",      "1-999"),
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
    """向後相容：只回 1,000,001+ 等級的 (人數, 股數)"""
    levels = query_stock_all_levels(opener, token, code, date)
    return levels.get("1000k+", (0, 0))


def query_stock_all_levels(opener, token, code, date):
    """一次 HTML 響應抓 7 個等級。回傳 {level_key: (holders, shares), ...}"""
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

    levels = {}
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    for row in rows:
        cell_html = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        # 保留逗號以辨識範圍字串
        cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cell_html]
        if len(cells) < 4:
            continue
        range_label = cells[1]  # 例如 "1,000,001以上" 或 "50,001-100,000"
        for key, marker, _ in LEVEL_DEFS:
            if key in levels:
                continue
            if marker in range_label:
                try:
                    h = int(cells[2].replace(',', ''))
                    s = int(cells[3].replace(',', ''))
                    levels[key] = (h, s)
                except:
                    pass
                break
    return levels

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
    now = datetime.now(TAIPEI_TZ)

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

    # 讀取現有資料（保留 total_s + 失敗時的 fallback）
    existing_total = {}
    existing_rows = {}
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            old = json.load(f)
        for r in old.get("data", []):
            existing_total[r["code"]] = r.get("total_s", 0)
            existing_rows[r["code"]] = r

    results = []
    ok, fail = 0, []

    for code, name in COMPANIES:
        print(f"\n  [{code}] {name}...", end=" ", flush=True)
        try:
            # 重新取 token（每次查詢需要新 token）
            opener2, token2 = get_page_token({})
            curr_levels = query_stock_all_levels(opener2, token2, code, curr_date_raw)

            opener3, token3 = get_page_token({})
            prev_levels = query_stock_all_levels(opener3, token3, code, prev_date_raw)

            total_s = existing_total.get(code, 0)
            if total_s == 0:
                opener4, token4 = get_page_token({})
                total_s = get_total_shares(opener4, token4, code, curr_date_raw)

            # 組合每個等級的 curr/prev 資料
            levels_data = {}
            for key, _, _ in LEVEL_DEFS:
                ch, cs = curr_levels.get(key, (0, 0))
                ph, ps = prev_levels.get(key, (0, 0))
                levels_data[key] = {
                    "curr_h": ch, "curr_s": cs,
                    "prev_h": ph, "prev_s": ps,
                }

            # 千張資料（向後相容：頂層平鋪欄位）
            top = levels_data.get("1000k+", {"curr_h": 0, "curr_s": 0, "prev_h": 0, "prev_s": 0})
            results.append({
                "code": code, "name": name,
                "curr_h": top["curr_h"], "curr_s": top["curr_s"],
                "prev_h": top["prev_h"], "prev_s": top["prev_s"],
                "total_s": total_s,
                "levels": levels_data,
            })
            # 列印 7 個等級的人數變化（簡短版）
            level_brief = []
            for key, _, label in LEVEL_DEFS:
                lv = levels_data[key]
                dh = lv["curr_h"] - lv["prev_h"]
                sign = f"+{dh}" if dh > 0 else (str(dh) if dh < 0 else "=")
                level_brief.append(f"{key.split('-')[0]}:{lv['curr_h']}({sign})")
            print(" | ".join(level_brief))
            ok += 1
        except Exception as e:
            print(f"❌ {e}")
            fail.append(f"{name}({code})")
            # ☆ 失敗時保留舊資料
            old_row = existing_rows.get(code)
            if old_row:
                results.append(old_row)
                print(f"           ↳ 保留上次資料")

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

    # 本週 snapshot（包含千張 + 全部 7 個等級）
    new_snapshot = {
        "date": curr_date,
        "rawDate": curr_date_raw,
        "data": [
            {
                "code": r["code"], "name": r["name"],
                "h": r["curr_h"], "s": r["curr_s"],  # 向後相容（千張）
                "total_s": r["total_s"],
                "levels": {
                    key: {"h": lv["curr_h"], "s": lv["curr_s"]}
                    for key, lv in (r.get("levels") or {}).items()
                },
            }
            for r in results
        ],
    }

    # 移除同日期的舊紀錄（若已存在），再插入到最前
    weeks = [w for w in history.get("weeks", []) if w.get("date") != curr_date]
    weeks.insert(0, new_snapshot)
    history["weeks"] = weeks[:MAX_WEEKS]  # 限制歷史長度

    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, separators=(",", ":"))

    # 更新狀態
    try:
        from _status_helper import update_status
        update_status("holders", {"dataDate": curr_date})
    except Exception as e:
        print(f"⚠️ 狀態更新失敗：{e}")

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
