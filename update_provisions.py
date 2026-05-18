#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_provisions.py
🌾 AI 評估糧草先行（PROVISIONS-FIRST score）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
篩選「今年解盲且即將發生」的公司，
依據 6 個維度評估「兵馬未動，糧草先行」分數，
幫投資人在低價/平穩期提前佈局現金。

評分維度（總分 100）：
  催化迫近 30% + 股價窗口 20% + 臨床訊號 20%
  + 現金狀態 10% + 新聞熱度 10% + 成功機率 10%

輸出：provisions.json
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import json, os, sys
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

TAIPEI_TZ = timezone(timedelta(hours=8))
HERE = os.path.dirname(os.path.abspath(__file__))
DATE_PATH = os.path.join(HERE, "date.json")
CF_PATH = os.path.join(HERE, "cashflow.json")
NEWS_PATH = os.path.join(HERE, "news_status.json")
SCORES_PATH = os.path.join(HERE, "scores.json")
OUT_PATH = os.path.join(HERE, "provisions.json")


# ─────────────────────────────────────────────
# 解析事件預計日期
# ─────────────────────────────────────────────
def parse_event_date(event, quarter_key):
    """從 expectedDisclosureNote / announcedNote / 季度推估日期"""
    today = datetime.now(TAIPEI_TZ).date()
    year = today.year

    # 1. 先看 expectedDisclosureNote 是否有具體季度
    note = (event.get("expectedDisclosureNote") or "") + (event.get("announcedNote") or "")
    # "預計2026年Q2 公布..." / "2026 台灣 Phase III 完成..."
    import re
    m = re.search(r'2026.*?Q([1-4])', note)
    if m:
        q = int(m.group(1))
        return datetime(year, q*3 - 1, 15, tzinfo=TAIPEI_TZ).date()
    m = re.search(r'2026[年/-](\d{1,2})[/月-](\d{1,2})', note)
    if m:
        try:
            return datetime(year, int(m.group(1)), int(m.group(2)), tzinfo=TAIPEI_TZ).date()
        except Exception:
            pass
    if '2026年底' in note or '2026 年底' in note or '年底前' in note:
        return datetime(year, 12, 15, tzinfo=TAIPEI_TZ).date()
    if '上半年' in note or 'H1' in note:
        return datetime(year, 6, 15, tzinfo=TAIPEI_TZ).date()

    # 2. 回退用季度中段
    q_dates = {
        "q1": datetime(year, 2, 15),
        "q2": datetime(year, 5, 15),
        "q3": datetime(year, 8, 15),
        "q4": datetime(year, 11, 15),
        "h2": datetime(year, 9, 30),
    }
    d = q_dates.get(quarter_key.lower())
    return d.date() if d else today


# ─────────────────────────────────────────────
# 6 個評分維度
# ─────────────────────────────────────────────
def score_imminence(days_until):
    """⏰ 催化迫近：越快越高"""
    if days_until < 0:
        # 已過期但事件可能延後揭露：仍給中等分數
        if days_until > -14:
            return 60
        return max(0, 30 + days_until)  # 30 天後降至 0
    if days_until <= 7:
        return 100
    if days_until <= 30:
        return 100 - (days_until - 7) * 0.5     # 91.5
    if days_until <= 90:
        return 88 - (days_until - 30) * 0.4     # 64
    if days_until <= 180:
        return 64 - (days_until - 90) * 0.45    # 24
    return max(0, 25 - (days_until - 180) * 0.1)


def score_price_window(price_history):
    """💹 股價窗口：低位置 + 穩定 = 適合佈局"""
    if not price_history or len(price_history) < 5:
        return 50  # 資料不足，中性
    prices = [p.get("close", 0) for p in price_history if p.get("close")]
    if len(prices) < 5:
        return 50
    current = prices[-1]
    p_max = max(prices)
    p_min = min(prices)
    if p_max == p_min:
        return 60

    # 百分位置（0=240日低點, 100=240日高點）
    percentile = (current - p_min) / (p_max - p_min) * 100

    # 位置分（低=好，因為佈局空間大）
    if percentile <= 25:    pos = 100
    elif percentile <= 40:  pos = 85
    elif percentile <= 55:  pos = 70
    elif percentile <= 70:  pos = 55
    elif percentile <= 85:  pos = 35
    else:                   pos = 15  # 接近高點，佈局風險高

    # 20 日波動度（std / mean × 100，越小越穩）
    last_20 = prices[-20:] if len(prices) >= 20 else prices
    mean = sum(last_20) / len(last_20)
    std = (sum((p - mean)**2 for p in last_20) / len(last_20)) ** 0.5
    vol_pct = (std / mean * 100) if mean else 0

    if vol_pct < 3:    vol_score = 100  # 極穩
    elif vol_pct < 6:  vol_score = 80
    elif vol_pct < 10: vol_score = 60
    elif vol_pct < 15: vol_score = 35
    else:              vol_score = 15  # 高波動

    # 60% 位置 + 40% 穩定度
    return round(pos * 0.6 + vol_score * 0.4, 1), percentile, vol_pct


def score_clinical(event):
    """🧬 臨床訊號：收案/期中/催化"""
    score = 40  # 基礎

    # 已公布實績（最強訊號）
    if event.get("announcedNote"):
        ann = event.get("announcedNote", "")
        if any(k in ann for k in ["收案完成", "期中分析通過", "IDMC", "解盲", "達標"]):
            score += 30
        else:
            score += 15

    # 催化強度
    cl = event.get("catalystLevel", "")
    score += {"高": 20, "中高": 12, "中": 6, "中低": 2, "低": 0}.get(cl, 0)

    # 期別越後越穩
    label = event.get("label", "")
    if "3期" in label or "三期" in label:    score += 12
    elif "2b" in label:                       score += 8
    elif "2期" in label or "二期" in label:   score += 5
    elif "1b" in label:                       score += 3

    # 投資亮點數量（公司資訊豐富 = 投資人能看清楚）
    bf = event.get("bonusFactors", [])
    if bf: score += min(8, len(bf))

    return min(100, score)


def score_cash(cf_entry, op_cf_neg=True):
    """💰 現金狀態：能撐就好，已增資加分"""
    c25 = (cf_entry.get("cash_2025") or {}).get("value", 0)
    c26 = (cf_entry.get("cash_2026") or {}).get("value", 0)
    c24 = (cf_entry.get("cash_2024") or {}).get("value", 0)

    # 取最新
    latest = c26 or c25 or c24 or 0

    # 基礎分依現金規模
    if latest >= 100e8:    base = 95   # ≥100億
    elif latest >= 50e8:   base = 88
    elif latest >= 20e8:   base = 78
    elif latest >= 10e8:   base = 68
    elif latest >= 5e8:    base = 55
    elif latest >= 2e8:    base = 42
    elif latest >= 1e8:    base = 30
    else:                  base = 15

    # 增資加分：2026 > 2025 表示剛完成增資
    if c26 and c25 and c26 > c25 * 1.5:
        base = min(100, base + 12)

    # 連續燒錢但 cash 還夠 = 健康燒錢做臨床（理想狀態）
    if c25 and c24 and c25 < c24 and latest > 3e8:
        base = min(100, base + 5)  # 燒錢中但仍有 runway

    return base


def score_news(news_entry, event):
    """📡 新聞熱度：近期關注 = 市場開始注意"""
    cnt = (news_entry or {}).get("count", 0)

    if cnt >= 8:   base = 100
    elif cnt >= 5: base = 85
    elif cnt >= 3: base = 65
    elif cnt >= 1: base = 45
    else:          base = 25

    if event.get("highlightThisWeek"):
        base = min(100, base + 15)

    return base


def score_success_prob(scores_entry, event):
    """📊 成功機率：取 update_scores 的 clinicalCredibility"""
    if not scores_entry:
        return 50
    cc = scores_entry.get("components", {}).get("clinicalCredibility", 50)

    # 期別後段加成
    label = event.get("label", "")
    if "3期" in label or "三期" in label:
        cc = min(100, cc + 8)

    return cc


# ─────────────────────────────────────────────
# 找符合「糧草先行」精神的事件
# ─────────────────────────────────────────────
UNBLIND_TAGS = {"tag-resolve", "tag-data"}
UNBLIND_KEYWORDS = ["解盲", "期中分析", "試驗結果", "療效評估", "讀出", "完成收案", "數據公布"]

def find_provisions_candidate_event(company):
    """從公司 events 中找出最值得提前佈局的事件
    優先順序：tag-resolve > tag-data 含解盲關鍵字 > 任何 tag-data
    """
    events = company.get("events", {}) or {}
    today = datetime.now(TAIPEI_TZ).date()

    candidates = []
    for q, ev in events.items():
        if not ev:
            continue
        tag = ev.get("tag", "")
        label = ev.get("label", "")
        # 解盲類事件
        if tag == "tag-resolve":
            priority = 3
        elif tag == "tag-data" and any(k in label for k in UNBLIND_KEYWORDS):
            priority = 2
        elif tag == "tag-data":
            priority = 1
        else:
            continue

        ev_date = parse_event_date(ev, q)
        days_until = (ev_date - today).days
        candidates.append((priority, days_until, q, ev, ev_date))

    if not candidates:
        return None

    # 排序：優先序高 → 天數越近（但已過很久的扣分）
    # 我們希望取「最快發生的解盲類事件」，但若全是過期事件，要選最近過期的
    def sort_key(c):
        priority, days, q, ev, ev_date = c
        # 天數權重：取絕對值小的，但未來事件加優先
        if days < -30:
            return (-priority, 1000)  # 超期遠端 = 最後
        elif days < 0:
            return (-priority, 500 + abs(days))  # 過期但近
        else:
            return (-priority, days)  # 未來事件：越近越前

    candidates.sort(key=sort_key)
    return candidates[0]


# ─────────────────────────────────────────────
# 主程式
# ─────────────────────────────────────────────
def main():
    print("=" * 60)
    print(" 🌾 AI 評估糧草先行 (PROVISIONS-FIRST SCORE)")
    print("=" * 60)

    # 載入資料
    with open(DATE_PATH, "r", encoding="utf-8") as f:
        date_data = json.load(f)
    with open(CF_PATH, "r", encoding="utf-8") as f:
        cf_data = json.load(f).get("companies", {})
    try:
        with open(NEWS_PATH, "r", encoding="utf-8") as f:
            news_data = json.load(f).get("companies", {})
    except Exception:
        news_data = {}
    try:
        with open(SCORES_PATH, "r", encoding="utf-8") as f:
            scores_data = json.load(f).get("companies", {})
    except Exception:
        scores_data = {}

    results = []
    for sec in date_data:
        for c in sec.get("companies", []):
            code = c.get("code")
            name = c.get("name")

            # 找最值得提前佈局的事件
            cand = find_provisions_candidate_event(c)
            if not cand:
                continue
            priority, days_until, quarter, event, ev_date = cand

            # 算 6 個維度分數
            imm = score_imminence(days_until)
            pw_result = score_price_window(c.get("priceHistory", []))
            if isinstance(pw_result, tuple):
                pw, percentile, vol_pct = pw_result
            else:
                pw, percentile, vol_pct = pw_result, None, None
            cl = score_clinical(event)
            cs = score_cash(cf_data.get(code, {}))
            ns = score_news(news_data.get(code), event)
            sp = score_success_prob(scores_data.get(code), event)

            # 加權總分
            total = round(
                imm * 0.30 +
                pw  * 0.20 +
                cl  * 0.20 +
                cs  * 0.10 +
                ns  * 0.10 +
                sp  * 0.10,
                1
            )

            # 建議文字
            advice = []
            if percentile is not None and percentile < 35:
                advice.append("股價偏低")
            elif percentile is not None and percentile < 60:
                advice.append("股價平穩")
            if vol_pct is not None and vol_pct < 5:
                advice.append("波動小")
            if days_until <= 60 and days_until >= 0:
                advice.append(f"{days_until}天內解盲")
            elif days_until < 0:
                advice.append("延期中")
            else:
                advice.append(f"預計{days_until}天")
            if event.get("highlightThisWeek"):
                advice.append("本週重點")

            results.append({
                "code": code,
                "name": name,
                "provisionScore": total,
                "components": {
                    "imminence": round(imm, 1),
                    "priceWindow": round(pw, 1),
                    "clinical": round(cl, 1),
                    "cash": round(cs, 1),
                    "newsHeat": round(ns, 1),
                    "successProb": round(sp, 1),
                },
                "event": {
                    "quarter": quarter.upper(),
                    "tag": event.get("tag"),
                    "label": event.get("label"),
                    "drug": event.get("drug"),
                    "daysUntil": days_until,
                    "expectedDate": event.get("expectedDisclosureNote") or event.get("announcedNote") or "",
                    "highlightThisWeek": bool(event.get("highlightThisWeek")),
                },
                "priceStatus": {
                    "percentile": round(percentile, 1) if percentile is not None else None,
                    "volatility": round(vol_pct, 1) if vol_pct is not None else None,
                },
                "advice": " · ".join(advice) if advice else "—",
            })

    # 依總分排序
    results.sort(key=lambda r: -r["provisionScore"])

    # 輸出 TOP 10（前端只顯示 TOP N，但我們存全部）
    print(f"\n找到 {len(results)} 家有解盲類事件的公司，TOP 10：")
    print(f"{'排名':<4} {'代號':<6} {'公司':<12} {'糧草分':<7} {'迫近':<5} {'股價':<5} {'臨床':<5} {'現金':<5} {'新聞':<5} {'機率':<5}")
    print("-" * 90)
    for i, r in enumerate(results[:10], 1):
        co = r["components"]
        print(f"{i:<4} {r['code']:<6} {r['name']:<12} {r['provisionScore']:<7} "
              f"{co['imminence']:<5} {co['priceWindow']:<5} {co['clinical']:<5} "
              f"{co['cash']:<5} {co['newsHeat']:<5} {co['successProb']:<5}")
        print(f"      ↳ {r['event']['quarter']} {r['event']['drug'] or '-'} «{r['event']['label']}» ({r['advice']})")

    # 寫入 JSON
    now = datetime.now(TAIPEI_TZ)
    output = {
        "lastRun": now.strftime("%Y/%m/%d %H:%M"),
        "tz": "UTC+8",
        "totalCompanies": len(results),
        "candidates": results,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))
    print(f"\n📁 寫入 {OUT_PATH}")

    # 狀態
    try:
        from _status_helper import update_status
        update_status("provisions")
    except Exception:
        pass


if __name__ == "__main__":
    main()
