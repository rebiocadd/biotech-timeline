#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_news.py - 每日自動掃描公司臨床進度新聞
資料來源：Google News RSS
執行時機：每天上午 08:00 TST

用法：
  python update_news.py          # 更新 news_status.json
  python update_news.py --push   # 更新後自動 git commit & push
"""

import json, re, sys, os, subprocess
import urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone, timedelta

# 強制 stdout 用 UTF-8（避開 Windows cp950 無法顯示 emoji）
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

TAIPEI_TZ = timezone(timedelta(hours=8))   # UTC+8

JSON_PATH = os.path.join(os.path.dirname(__file__), "news_status.json")
SUMMARY_PATH = os.path.join(os.path.dirname(__file__), "news_summary.json")
DATE_PATH = os.path.join(os.path.dirname(__file__), "date.json")
DAYS_FRESH = 14  # 14天內的新聞算「新動態」

# 臨床相關關鍵字（命中才算臨床新聞）
CLINICAL_KEYWORDS = [
    "解盲", "臨床", "試驗", "收案", "人體",
    "授權", "合作", "藥證", "核准", "申請",
    "FDA", "EMA", "IND", "NDA", "BTD",
    "Phase", "一期", "二期", "三期", "1期", "2期", "3期", "IIa", "IIb",
    "突破", "里程碑", "療效", "ORR", "PFS", "OS",
    "新藥", "細胞", "ADC", "CAR-T", "基因",
    "AACR", "ASCO", "ASH", "ESMO",
]

# 重要性評分 keyword 字典（影響「📰 27 家最新新聞」排序）
NEWS_IMPORTANCE_KEYWORDS = {
    # 🔴 極重要：催化兌現（直接影響股價）
    "high": [
        "解盲", "期中分析", "IDMC", "達標", "通過", "DSMB",
        "藥證", "核准", "獲准", "BTD", "突破性",
        "授權", "簽約", "里程碑",
        "收案完成", "完成收案", "達主要終點",
    ],
    # 🟠 中等：進度更新（中期影響）
    "medium": [
        "啟動", "申請", "送件", "進入", "推進",
        "合作", "策略夥伴", "Term Sheet",
        "Phase 1", "Phase 2", "Phase 3", "1期", "2期", "3期",
        "FDA", "EMA", "TFDA", "IND", "NDA",
        "ORR", "PFS", "OS", "療效",
        "AACR", "ASCO", "ASH", "ESMO",  # 重要會議
    ],
    # ⚪ 一般：例行公告
    "low": [
        "法說", "說明會", "投資人", "財報",
        "更換", "人事", "改名", "增資", "募資",
    ],
}

def score_news_importance(title):
    """計算新聞重要性等級
    回傳：('high'|'medium'|'low', [hit keywords])
    """
    if not title:
        return ('low', [])
    high_hits = [k for k in NEWS_IMPORTANCE_KEYWORDS["high"] if k in title]
    if high_hits:
        return ('high', high_hits)
    med_hits = [k for k in NEWS_IMPORTANCE_KEYWORDS["medium"] if k in title]
    if med_hits:
        return ('medium', med_hits)
    low_hits = [k for k in NEWS_IMPORTANCE_KEYWORDS["low"] if k in title]
    return ('low', low_hits)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

def load_companies():
    """從 date.json 讀取所有公司清單"""
    with open(DATE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    companies = []
    for section in data:
        for c in section["companies"]:
            companies.append((c["code"], c["name"]))
    return companies

def fetch_rss(query):
    """抓取 Google News RSS"""
    url = (
        "https://news.google.com/rss/search?"
        + urllib.parse.urlencode({
            "q": query,
            "hl": "zh-TW",
            "gl": "TW",
            "ceid": "TW:zh-Hant",
        })
    )
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", errors="ignore")

def parse_rss(xml_text):
    """簡單 regex 解析 RSS items"""
    items = []
    for m in re.finditer(r"<item>(.*?)</item>", xml_text, re.DOTALL):
        block = m.group(1)
        def take(tag):
            mm = re.search(rf"<{tag}>(.*?)</{tag}>", block, re.DOTALL)
            return mm.group(1).strip() if mm else ""
        title = take("title")
        # 移除 CDATA 包裝
        title = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", title)
        link = take("link")
        pub = take("pubDate")
        items.append({"title": title, "link": link, "pubDate": pub})
    return items

def parse_rss_date(s):
    """解析 RSS 日期：Wed, 14 May 2026 06:30:00 GMT"""
    try:
        return datetime.strptime(s, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
    except Exception:
        try:
            return datetime.strptime(s, "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=timezone.utc)
        except Exception:
            return None

def is_clinical(title):
    return any(kw in title for kw in CLINICAL_KEYWORDS)

def scan_company(code, name):
    """掃描單家公司的最新臨床新聞"""
    try:
        xml = fetch_rss(f"{name} {code}")
    except Exception as e:
        return {"error": str(e), "news": []}

    items = parse_rss(xml)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)

    fresh_news = []
    for it in items[:15]:
        pub = parse_rss_date(it["pubDate"])
        if not pub or pub < cutoff:
            continue
        if not is_clinical(it["title"]):
            continue
        # 將 UTC 新聞時間轉為 UTC+8 顯示
        pub_taipei = pub.astimezone(TAIPEI_TZ)
        fresh_news.append({
            "title": it["title"][:120],
            "link": it["link"],
            "date": pub_taipei.strftime("%m/%d"),
            "ts": int(pub.timestamp()),
        })

    fresh_news.sort(key=lambda x: x["ts"], reverse=True)
    return {"news": fresh_news[:5]}

def main():
    auto_push = "--push" in sys.argv
    now = datetime.now(TAIPEI_TZ)
    today_str = now.strftime("%Y/%m/%d")
    today_short = now.strftime("%m/%d")
    run_time = now.strftime("%Y/%m/%d %H:%M")

    print("=" * 55)
    print(" 每日臨床新聞掃描")
    print(f" 執行時間：{run_time}")
    print("=" * 55)

    companies = load_companies()
    print(f"\n共 {len(companies)} 家公司")

    result = {
        "lastRun": run_time,
        "lastRunDate": today_short,
        "freshDays": DAYS_FRESH,
        "companies": {},
    }
    has_news_count = 0

    for code, name in companies:
        print(f"  [{code}] {name}...", end=" ", flush=True)
        r = scan_company(code, name)
        if r.get("error"):
            print(f"❌ {r['error']}")
            result["companies"][code] = {"checked": today_short, "news": []}
            continue
        news = r["news"]
        result["companies"][code] = {
            "checked": today_short,
            "news": news,
        }
        if news:
            # 最新新聞日期
            latest = news[0]
            try:
                latest_ts = latest.get("ts", 0)
                days_ago = (datetime.now(timezone.utc).timestamp() - latest_ts) / 86400
                if days_ago <= DAYS_FRESH:
                    has_news_count += 1
                    print(f"🆕 {len(news)} 則（最新 {latest['date']}）")
                else:
                    print(f"舊 ({len(news)} 則)")
            except:
                print(f"{len(news)} 則")
        else:
            print("無臨床新聞")

    # 寫入結果（移除中間用的 ts 欄位）
    for code in result["companies"]:
        for n in result["companies"][code]["news"]:
            n.pop("ts", None)

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))

    # ───────────────────────────────────────────
    # 📰 生成「最新新聞摘要」(news_summary.json)
    # 每家公司挑一條最重要的新聞，依重要性 → 新舊排序
    # ───────────────────────────────────────────
    name_map = {code: name for code, name in companies}
    summary_rows = []
    importance_rank = {'high': 0, 'medium': 1, 'low': 2}
    for code, name in companies:
        comp = result["companies"].get(code, {})
        news = comp.get("news", [])
        if not news:
            summary_rows.append({
                "code": code, "name": name,
                "importance": "none", "rankIdx": 3,
                "topNews": None, "newsCount": 0,
            })
            continue
        # 對每條新聞評重要性，挑最高的（同級則取最新；news 已按 ts 降冪排序）
        scored = []
        for i, n in enumerate(news):
            level, hits = score_news_importance(n.get("title", ""))
            scored.append({
                "title": n.get("title"),
                "link": n.get("link"),
                "date": n.get("date"),
                "level": level,
                "hits": hits,
                "rank": importance_rank[level],
                "order": i,  # 原始順序（i 越小越新）
            })
        scored.sort(key=lambda x: (x['rank'], x['order']))
        top = scored[0]
        summary_rows.append({
            "code": code, "name": name,
            "importance": top['level'],
            "rankIdx": top['rank'],
            "topNews": {
                "title": top['title'],
                "link": top['link'],
                "date": top['date'],
                "tags": top['hits'][:4],  # 最多顯示 4 個 keyword 標籤
            },
            "newsCount": len(news),
        })

    # 排序：重要性高 → 新聞數多 → 代號
    summary_rows.sort(key=lambda r: (r['rankIdx'], -r['newsCount'], r['code']))

    summary = {
        "lastRun": run_time,
        "lastRunDate": today_short,
        "tz": "UTC+8",
        "companies": summary_rows,
    }
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, separators=(",", ":"))

    high_cnt = sum(1 for r in summary_rows if r['importance'] == 'high')
    med_cnt = sum(1 for r in summary_rows if r['importance'] == 'medium')
    low_cnt = sum(1 for r in summary_rows if r['importance'] == 'low')
    none_cnt = sum(1 for r in summary_rows if r['importance'] == 'none')
    print(f"\n 📰 新聞重要性分布：🔴 {high_cnt}  🟠 {med_cnt}  ⚪ {low_cnt}  —  {none_cnt}")
    print(f" 📁 寫入摘要 {SUMMARY_PATH}")

    # 更新狀態
    try:
        from _status_helper import update_status
        update_status("news")
    except Exception as e:
        print(f"⚠️ 狀態更新失敗：{e}")

    print(f"\n{'='*55}")
    print(f" ✅ 掃描完成")
    print(f" 🆕 {has_news_count} 家公司有 {DAYS_FRESH} 天內新聞")
    print(f" 📁 已寫入 {JSON_PATH}")
    print("=" * 55)

    if auto_push:
        print("\n🚀 自動 git commit & push...")
        os.chdir(os.path.dirname(__file__))
        subprocess.run(["git", "add", "news_status.json"], check=True)
        try:
            subprocess.run(["git", "commit", "-m", f"每日新聞掃描 {today_str}"], check=True)
            subprocess.run(["git", "push", "origin", "main"], check=True)
            print("✅ 已推送至 GitHub")
        except subprocess.CalledProcessError:
            print("⚠️ 無變更或推送失敗")

if __name__ == "__main__":
    main()
