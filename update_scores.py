#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_scores.py - 動態投資評分引擎 (Backend)

每日從現有資料源計算每家公司的 InvestmentScore：
- date.json: 催化事件、臨床階段、藥物資訊
- holders.json: 千張大戶、總股東變化
- cashflow.json: 現金餘額、燒錢速度
- news_status.json: 新聞情緒、近期動態
- date.json (price/priceHistory): 股價趨勢

輸出：scores.json (含 score_history)

權重來自 config/scoringWeights.json (可隨時調整)
所有 scoring 函數獨立、可單獨呼叫測試
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

TAIPEI_TZ = timezone(timedelta(hours=8))
BASE = os.path.dirname(__file__)
PATHS = {
    "weights":  os.path.join(BASE, "config", "scoringWeights.json"),
    "date":     os.path.join(BASE, "date.json"),
    "holders":  os.path.join(BASE, "holders.json"),
    "holders_history": os.path.join(BASE, "holders_history.json"),
    "cashflow": os.path.join(BASE, "cashflow.json"),
    "news":     os.path.join(BASE, "news_status.json"),
    "scores":   os.path.join(BASE, "scores.json"),
}

# ─────────────────────────────────────────────
# 工具函式
# ─────────────────────────────────────────────
def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, v))

def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ─────────────────────────────────────────────
# 評分模組 (每個獨立可調整)
# ─────────────────────────────────────────────
def calculate_catalyst_score(company, weights):
    """A1: 催化事件分數
    依據事件類型、距離事件天數、臨床期別、狀態給分。
    """
    cfg = weights["catalyst"]
    events = company.get("events", {}) or {}
    today = datetime.now(TAIPEI_TZ).date()

    max_score = 0
    contributing = []
    for q, ev in events.items():
        if not ev:
            continue
        tag = ev.get("tag", "")
        base = cfg["eventTypeWeights"].get(tag, 30)

        # 預估時間（粗略：當季中段）
        q_dates = {
            "q1": datetime(today.year, 2, 15, tzinfo=TAIPEI_TZ).date(),
            "q2": datetime(today.year, 5, 15, tzinfo=TAIPEI_TZ).date(),
            "q3": datetime(today.year, 8, 15, tzinfo=TAIPEI_TZ).date(),
            "q4": datetime(today.year, 11, 15, tzinfo=TAIPEI_TZ).date(),
            "h2": datetime(today.year, 9, 30, tzinfo=TAIPEI_TZ).date(),
        }
        ev_date = q_dates.get(q.lower(), today)
        days_diff = (ev_date - today).days

        # 時間鄰近係數
        if days_diff < 7 and days_diff > -7:
            prox = cfg["timeProximityBoost"]["within7d"]
        elif days_diff < 30:
            prox = cfg["timeProximityBoost"]["within30d"]
        elif days_diff < 90:
            prox = cfg["timeProximityBoost"]["within90d"]
        elif days_diff < 180:
            prox = cfg["timeProximityBoost"]["within180d"]
        else:
            prox = cfg["timeProximityBoost"]["beyond180d"]

        # 臨床期別係數（看 ev.label）
        label = ev.get("label", "")
        clin = 1.0
        for stage, mul in cfg["clinicalStageBoost"].items():
            if stage in label:
                clin = mul
                break

        # 狀態係數
        status = ev.get("statusLabel") or ev.get("status", "")
        stat_mul = cfg["statusMultiplier"].get(status, 1.0)

        # highlight 加碼
        hl = cfg["highlightThisWeekBoost"] if ev.get("highlightThisWeek") else 1.0

        score = base * prox * clin * stat_mul * hl
        contributing.append((q.upper(), score, base, prox, clin, stat_mul))
        if score > max_score:
            max_score = score

    return clamp(max_score), contributing


def calculate_cash_runway_score(company, cashflow_entry, weights):
    """A2: 現金 runway 分數"""
    cfg = weights["cashRunway"]
    cash = (cashflow_entry.get("cash_2026") or cashflow_entry.get("cash_2025") or {}).get("value")
    ocf_entry = cashflow_entry.get("cf_2025") or cashflow_entry.get("cf_2026") or {}
    ocf = ocf_entry.get("operating_cf")

    # 若 OCF 為正（賺錢），直接給高分
    if ocf is not None and ocf > 0:
        return 90, {"runway_months": None, "ocf_positive": True}

    # 算 runway months
    months = None
    if cash and ocf and ocf < 0:
        monthly_burn = abs(ocf) / 12
        months = cash / monthly_burn if monthly_burn > 0 else None

    if months is None:
        # 無 OCF 資料，純看現金部位（>10億給中等分）
        if cash is None:
            return 50, {"runway_months": None, "fallback": True}
        if cash >= 1e9:    score = 70
        elif cash >= 5e8:  score = 55
        elif cash >= 1e8:  score = 40
        else:              score = 25
        return score, {"runway_months": None, "cash_only": True, "cash": cash}

    th = cfg["monthThresholds"]
    sm = cfg["scoreMap"]
    if months >= th["excellent"]:      score = sm["excellent"]
    elif months >= th["good"]:         score = sm["good"]
    elif months >= th["moderate"]:     score = sm["moderate"]
    elif months >= th["warning"]:      score = sm["warning"]
    else:                              score = sm["critical"]

    return clamp(score), {"runway_months": months, "cash": cash, "ocf": ocf}


def calculate_price_position_score(company, weights):
    """A3: 股價位置分數（用 240 日高點與精確 20 日漲幅）"""
    cfg = weights["pricePosition"]
    hist = company.get("priceHistory", []) or []
    if len(hist) < 2:
        return 50, {"reason": "no price history"}

    closes = [p["close"] for p in hist if p.get("close")]
    if not closes:
        return 50, {"reason": "no closes"}

    curr = closes[-1]
    high_240d = max(closes)  # 全部資料的最大值 = 240 日高點（若有 240 筆）
    pct_below_high = (high_240d - curr) / high_240d * 100 if high_240d > 0 else 0

    # 距離高點分數
    score = 60
    if pct_below_high < 5:    score = cfg["distFromHigh_scoreMap"]["withinPct5"]
    elif pct_below_high < 15: score = cfg["distFromHigh_scoreMap"]["withinPct15"]
    elif pct_below_high < 30: score = cfg["distFromHigh_scoreMap"]["withinPct30"]
    elif pct_below_high < 50: score = cfg["distFromHigh_scoreMap"]["withinPct50"]
    else:                     score = cfg["distFromHigh_scoreMap"]["beyondPct50"]

    # 精確 20 日漲幅（若資料 ≥ 21 筆，取 -21 位的價格做基準）
    if len(closes) >= 21:
        base_20d = closes[-21]
        gain_20d = (curr - base_20d) / base_20d * 100 if base_20d else 0
    elif len(closes) >= 2:
        gain_20d = (curr - closes[0]) / closes[0] * 100 if closes[0] else 0
    else:
        gain_20d = None

    if gain_20d is not None:
        sp = cfg["shortTermSurge_penalty"]
        if gain_20d > 40:    score += sp["gain20d_gt40"]
        elif gain_20d > 25:  score += sp["gain20d_gt25"]
        elif gain_20d < 5:   score += sp["gain20d_lt5"]

    return clamp(score), {
        "gain_20d": gain_20d, "pct_below_high": pct_below_high,
        "data_points": len(closes), "high_240d": high_240d
    }


def calculate_trend_score(company, weights):
    """A4: 趨勢分數（簡化版：以現有 5 日資料計算）"""
    cfg = weights["trend"]
    hist = company.get("priceHistory", []) or []
    if len(hist) < 3:
        return 50, {"reason": "insufficient history"}

    closes = [p["close"] for p in hist if p.get("close")]
    if len(closes) < 3:
        return 50, {"reason": "no closes"}

    curr = closes[-1]
    ma_short = sum(closes[-3:]) / 3
    ma_long = sum(closes) / len(closes)

    # 簡化 MA 排列判斷
    if curr > ma_short > ma_long:
        score = cfg["maAlignment_above_ma60"]
    elif curr > ma_long:
        score = cfg["maAlignment_below_ma60"]
    elif curr < ma_short and curr < ma_long:
        score = cfg["maAlignment_perfect_bear"] + 20  # 軟化
    else:
        score = 50

    return clamp(score), {"curr": curr, "ma_short": ma_short, "ma_long": ma_long}


def calculate_shareholder_structure_score(company, holders_entry, weights):
    """A5: 籌碼結構分數"""
    cfg = weights["shareholder"]
    if not holders_entry:
        return 50, {"reason": "no holders data"}

    score = 50

    # 千張大戶人數變化
    dh = (holders_entry.get("curr_h", 0) - holders_entry.get("prev_h", 0))
    if dh > 0: score += cfg["bigHolderHolders_increase"]
    elif dh < 0: score += cfg["bigHolderHolders_decrease"]

    # 千張大戶持股變化
    ds = (holders_entry.get("curr_s", 0) - holders_entry.get("prev_s", 0))
    if ds > 0: score += cfg["bigHolderShares_increase"]
    elif ds < 0: score += cfg["bigHolderShares_decrease"]

    # 總股東變化
    dth = (holders_entry.get("total_h", 0) - holders_entry.get("prev_total_h", 0))
    if dth > 0: score += cfg["totalShareholder_increase"]
    elif dth < 0: score += cfg["totalShareholder_decrease"]

    return clamp(score), {
        "big_holders_change": dh,
        "big_shares_change": ds,
        "total_shareholders_change": dth,
    }


def calculate_news_sentiment_score(company, news_entry, weights):
    """A6: 新聞情緒分數"""
    cfg = weights["newsSentiment"]
    if not news_entry or not news_entry.get("news"):
        return cfg["noNewsScore"], {"news_count": 0}

    news_list = news_entry["news"]
    catalyst_keywords = ['核准', '藥證', '解盲', '期中分析', '療效', '授權', 'BTD', '突破性', '首付款']
    negative_keywords = ['失敗', '未達標', '駁回', '退回', '延後', '終止']

    catalyst_count = 0
    negative_count = 0
    for n in news_list:
        title = n.get("title", "")
        if any(k in title for k in catalyst_keywords):
            catalyst_count += 1
        if any(k in title for k in negative_keywords):
            negative_count += 1

    score = cfg["neutralNewsBaseline"]
    score += cfg["catalystNewsBonus"] * min(catalyst_count, 2) / 2  # 上限 2 則
    score += cfg["negativeNewsPenalty"] * min(negative_count, 2) / 2

    return clamp(score), {
        "news_count": len(news_list),
        "catalyst_count": catalyst_count,
        "negative_count": negative_count,
    }


def calculate_clinical_credibility_score(company, weights):
    """A7: 臨床可信度分數"""
    cfg = weights["clinicalCredibility"]
    events = company.get("events", {}) or {}

    # 找最高階段
    stage_score = 0
    for q, ev in events.items():
        if not ev:
            continue
        label = ev.get("label", "") + " " + ev.get("drug", "")
        for stage, pts in cfg["stagePoints"].items():
            if stage in label:
                stage_score = max(stage_score, pts)

    score = stage_score if stage_score else 50

    # 國際合作加分（從 detail / catalystReason / drug 找關鍵字）
    for q, ev in events.items():
        if not ev:
            continue
        all_text = " ".join([
            str(ev.get("detail", "")),
            str(ev.get("catalystReason", "")),
            str(ev.get("label", "")),
        ])
        if any(k in all_text for k in ["授權", "MOU", "Term Sheet", "簽署"]):
            score += cfg["internationalPartnerBonus"]
            break
    # 孤兒藥/BTD
    company_text = " ".join([
        company.get("strategy", ""),
        " ".join(str(ev.get("detail", "")) for ev in events.values() if ev)
    ])
    if "孤兒藥" in company_text: score += cfg["orphanDrugBonus"]
    if "突破性" in company_text or "BTD" in company_text: score += cfg["btdBonus"]

    return clamp(score), {"stage": stage_score}


# ─────────────────────────────────────────────
# 風險閘門
# ─────────────────────────────────────────────
def check_risk_gates(company, cashflow_entry, weights, runway_months, gain_20d, days_to_catalyst, price_gain_total):
    """回傳 list of risk flags"""
    cfg = weights["riskGates"]
    flags = []

    if runway_months is not None and runway_months < cfg["cashRunwayMonthsThreshold"]:
        flags.append({"code": "high_funding_risk", "label": "高增資風險", "severity": "high"})

    if gain_20d is not None and gain_20d > cfg["shortTermSurgePct"]:
        flags.append({"code": "short_term_overheated", "label": "短線過熱", "severity": "medium"})

    if (days_to_catalyst is not None and days_to_catalyst > cfg["catalystTooFarDays"]
        and price_gain_total is not None and price_gain_total > cfg["catalystTooFarPriceRisePct"]):
        flags.append({"code": "catalyst_too_far", "label": "催化太遠股價已超前", "severity": "medium"})

    return flags


# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────
def get_score_band(total, weights):
    """從高分到低分檢查，第一個 total >= min 的就是該 band。
    這樣可以處理小數分（如 79.2）落在 band gap (79-80) 的情況。"""
    sorted_bands = sorted(weights["scoreBands"], key=lambda b: b["min"], reverse=True)
    for band in sorted_bands:
        if total >= band["min"]:
            return band
    return sorted_bands[-1]


def main():
    now = datetime.now(TAIPEI_TZ)
    today_str = now.strftime("%Y/%m/%d")
    today_iso = now.strftime("%Y-%m-%d")
    print("=" * 60)
    print(" 動態投資評分引擎")
    print(f" 執行時間：{now.strftime('%Y/%m/%d %H:%M')} UTC+8")
    print("=" * 60)

    weights = load_json(PATHS["weights"])
    date_data = load_json(PATHS["date"], [])
    holders = load_json(PATHS["holders"], {})
    cashflow = load_json(PATHS["cashflow"], {})
    news = load_json(PATHS["news"], {})

    holders_by_code = {r["code"]: r for r in holders.get("data", [])}
    cashflow_by_code = (cashflow.get("companies") or {})
    news_by_code = (news.get("companies") or {})

    # 讀取舊 scores.json 保留 history
    old_scores = load_json(PATHS["scores"], {})
    history = old_scores.get("history", {})  # code → [{date, score, ...}, ...]

    weights_main = weights["totalWeights"]
    results = {}
    for sec in date_data:
        for c in sec["companies"]:
            code = c["code"]
            name = c["name"]
            print(f"\n  [{code}] {name}")

            cat_s, _ = calculate_catalyst_score(c, weights)
            cf_entry = cashflow_by_code.get(code, {})
            cash_s, cash_meta = calculate_cash_runway_score(c, cf_entry, weights)
            price_s, price_meta = calculate_price_position_score(c, weights)
            trend_s, _ = calculate_trend_score(c, weights)
            holders_entry = holders_by_code.get(code, {})
            shr_s, shr_meta = calculate_shareholder_structure_score(c, holders_entry, weights)
            news_entry = news_by_code.get(code, {})
            news_s, news_meta = calculate_news_sentiment_score(c, news_entry, weights)
            clin_s, _ = calculate_clinical_credibility_score(c, weights)

            total = (
                weights_main["catalyst"]            * cat_s +
                weights_main["cashRunway"]          * cash_s +
                weights_main["pricePosition"]       * price_s +
                weights_main["trend"]               * trend_s +
                weights_main["shareholder"]         * shr_s +
                weights_main["newsSentiment"]       * news_s +
                weights_main["clinicalCredibility"] * clin_s
            )
            total = round(clamp(total), 1)

            # 風險閘門
            flags = check_risk_gates(
                c, cf_entry, weights,
                runway_months=cash_meta.get("runway_months"),
                gain_20d=price_meta.get("gain_20d"),
                days_to_catalyst=None,  # TODO: 計算
                price_gain_total=None,
            )

            # 分數區段
            band = get_score_band(total, weights)

            scores = {
                "code": code,
                "name": name,
                "total": total,
                "band": band,
                "components": {
                    "catalyst":            round(cat_s, 1),
                    "cashRunway":          round(cash_s, 1),
                    "pricePosition":       round(price_s, 1),
                    "trend":               round(trend_s, 1),
                    "shareholder":         round(shr_s, 1),
                    "newsSentiment":       round(news_s, 1),
                    "clinicalCredibility": round(clin_s, 1),
                },
                "metadata": {
                    "cash_runway_months": cash_meta.get("runway_months"),
                    "cash":               cash_meta.get("cash"),
                    "gain_20d":           price_meta.get("gain_20d"),
                    "news_count":         news_meta.get("news_count", 0),
                    "shareholder_change": shr_meta.get("total_shareholders_change"),
                },
                "riskFlags": flags,
            }
            results[code] = scores

            # 更新歷史（每日一筆，相同日期覆蓋）
            h_list = history.get(code, [])
            h_list = [h for h in h_list if h.get("date") != today_iso]
            h_list.append({
                "date": today_iso,
                "total": total,
                "components": scores["components"],
                "band_label": band["label"],
            })
            # 保留最近 90 天
            h_list.sort(key=lambda x: x["date"])
            if len(h_list) > 90:
                h_list = h_list[-90:]
            history[code] = h_list

            print(f"    分數: {total:5.1f} ({band['label']}) | "
                  f"催化={cat_s:.0f} 現金={cash_s:.0f} 股價={price_s:.0f} "
                  f"趨勢={trend_s:.0f} 籌碼={shr_s:.0f} 新聞={news_s:.0f} 臨床={clin_s:.0f}"
                  + (f" ⚠️{len(flags)}" if flags else ""))

    output = {
        "lastRun": now.strftime("%Y/%m/%d %H:%M"),
        "tz": "UTC+8",
        "weightsVersion": weights.get("version", "1.0"),
        "companies": results,
        "history": history,
    }
    with open(PATHS["scores"], "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

    # 排序顯示 Top 10
    print("\n" + "=" * 60)
    print(" TOP 10 by InvestmentScore")
    print("=" * 60)
    top10 = sorted(results.values(), key=lambda x: -x["total"])[:10]
    for i, r in enumerate(top10, 1):
        flags_str = " ⚠️" + ",".join(f["label"] for f in r["riskFlags"]) if r["riskFlags"] else ""
        print(f"  {i:>2}. [{r['code']}] {r['name']:<10} {r['total']:>5.1f} ({r['band']['label']}){flags_str}")

    # 更新 status
    try:
        from _status_helper import update_status
        update_status("scores")
    except Exception:
        pass

    print(f"\n📁 寫入 {PATHS['scores']}")


if __name__ == "__main__":
    main()
