#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_highlights.py - 根據新聞自動標記事件為「本週值得注意」

執行時機：每日新聞掃描後（update_news.py 之後）

邏輯：
1. 從 news_status.json 讀取每家公司最近的臨床新聞
2. 計算新聞催化分數（關鍵字加權）
3. 配對到 date.json 的對應事件（藥名/標籤）
4. 強催化（≥10）自動標記為 highlightThisWeek
5. 弱催化或無新聞 → 清除舊的自動標記
6. 用 _autoSource 區分自動 vs 人工標記，永不覆蓋人工

用法：
  python update_highlights.py            # 更新 date.json
  python update_highlights.py --dry-run  # 模擬執行不寫檔
"""

import json
import re
import sys
import os
from datetime import datetime, timezone, timedelta

# 強制 stdout 用 UTF-8（避開 Windows cp950 無法顯示 emoji）
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

TAIPEI_TZ = timezone(timedelta(hours=8))
DATE_PATH = os.path.join(os.path.dirname(__file__), "date.json")
NEWS_PATH = os.path.join(os.path.dirname(__file__), "news_status.json")

# 觸發 highlight 的分數門檻
STRONG_THRESHOLD = 10

# ====== 強正面關鍵字（單則新聞命中即接近觸發） ======
STRONG_POSITIVE = {
    # 監管核准
    "獲核准": 15, "獲准": 13, "核准函": 15, "藥證核准": 15,
    "獲藥證": 14, "取得藥證": 14, "獲首張": 14, "首張藥證": 14,
    "BTD": 12, "突破性療法": 12, "突破性認定": 12,
    "獲孤兒藥": 11, "孤兒藥資格": 10,
    "通過上市": 12, "上市核准": 12, "上市審議通過": 11, "上市送件": 7,
    "獲准執行": 9, "獲准啟動": 9,
    # 試驗達標
    "解盲成功": 14, "解盲達標": 14, "達主要終點": 14, "達標": 11,
    "療效通過": 13, "療效達標": 13,
    "期中分析通過": 13, "IDMC通過": 13,
    "顯著意義": 11, "統計上顯著": 12, "正向結果": 11, "正面結果": 11,
    "完全緩解": 10, "CR": 4,
    # 商業里程碑
    "全球授權": 11, "獨家授權": 11, "授權簽約": 10, "簽署授權": 10,
    "Term Sheet": 8, "首付款": 9, "里程碑款": 8,
    "重要里程碑": 7, "重大里程碑": 8,
    # 試驗收案完成
    "收案完成": 7, "完成收案": 7, "完成最後給藥": 8,
}

# ====== 一般正面關鍵字 ======
POSITIVE = {
    "啟動": 4, "推進": 3, "進展": 3, "進入": 3, "完成": 4,
    "簽署": 4, "合作": 3, "聯合": 2, "MOU": 4,
    "投資": 3, "募資": 3, "增資": 2,
    "AACR": 5, "ASCO": 5, "ASH": 5, "ESMO": 5,
    "發表": 3, "口頭報告": 5, "海報發表": 4,
    "ORR": 3, "PFS": 3, "OS": 2,
    "突破": 5,
}

# ====== 負面關鍵字（清除標記或標記延後） ======
NEGATIVE = {
    "失敗": -15, "未達標": -14, "未達主要終點": -16, "未達": -10,
    "停止": -10, "暫停": -8, "終止": -10,
    "退回": -8, "駁回": -10, "補件": -5,
    "跌停": -3, "利空": -5, "下市": -10,
    "解盲未達": -16, "解盲失敗": -16,
    "撤回": -8, "撤銷": -8,
}


def score_news(title: str):
    """評分一則新聞。回傳 (分數, 命中關鍵字 list)"""
    score = 0
    hits = []
    for kw, w in STRONG_POSITIVE.items():
        if kw in title:
            score += w
            hits.append(kw)
    for kw, w in POSITIVE.items():
        if kw in title:
            score += w
            hits.append(kw)
    for kw, w in NEGATIVE.items():
        if kw in title:
            score += w
            hits.append(kw)
    return score, hits


def extract_drug_keywords(drug_str: str):
    """從 drug 欄位拆出藥名變體（如 'TMB-365/380' → ['TMB-365', 'TMB-380']）"""
    if not drug_str:
        return []
    # 拆 / 、 空格 、逗號
    parts = re.split(r"[/／\s,，、]+", drug_str)
    return [p.strip() for p in parts if p.strip() and len(p.strip()) >= 3]


def match_event(news_title: str, events: dict, company: dict):
    """配對新聞到最佳事件
    回傳 (quarter_key, event_obj, confidence) 或 None
    """
    candidates = []
    title_lower = news_title.lower()
    for q, ev in events.items():
        if ev is None:
            continue
        conf = 0
        # 1. 藥名匹配（高信心）
        drug_kws = extract_drug_keywords(ev.get("drug", ""))
        for kw in drug_kws:
            if kw.lower() in title_lower:
                conf += 6
        # 2. 適應症關鍵字
        indication = company.get("indication", "")
        if indication:
            for word in re.split(r"[、,，/／\s]+", indication):
                if len(word) >= 2 and word in news_title:
                    conf += 2
        # 3. 事件類型匹配（tag）
        tag = ev.get("tag", "")
        if tag == "tag-approval" and any(k in news_title for k in ["核准", "藥證", "上市", "送件", "突破性", "孤兒藥"]):
            conf += 3
        elif tag == "tag-resolve" and any(k in news_title for k in ["解盲", "期中分析", "IDMC", "顯著"]):
            conf += 3
        elif tag == "tag-data" and any(k in news_title for k in ["數據", "試驗", "療效", "ORR", "PFS"]):
            conf += 2
        elif tag == "tag-license" and any(k in news_title for k in ["授權", "MOU", "簽署", "合作"]):
            conf += 3
        elif tag == "tag-phase" and any(k in news_title for k in ["啟動", "推進", "收案", "三期", "二期"]):
            conf += 2
        elif tag == "tag-conference" and any(k in news_title for k in ["AACR", "ASCO", "ASH", "ESMO", "發表"]):
            conf += 3
        candidates.append((q, ev, conf))
    if not candidates:
        return None
    # 排序：先看 confidence，相同則優先當季 Q2
    candidates.sort(key=lambda x: (x[2], 1 if x[0] == "q2" else 0), reverse=True)
    top = candidates[0]
    if top[2] > 0:
        return top
    # 沒匹配 → 預設選當季 Q2
    for q, ev, _ in candidates:
        if q == "q2":
            return (q, ev, 0)
    return candidates[0]


def title_relevant(title: str, company_name: str, company_code: str) -> bool:
    """確認新聞標題真的在講這家公司（避免「浩鼎/鼎晉」混淆）"""
    if company_code in title:
        return True
    # 完整名稱命中
    if company_name in title:
        return True
    # 去除「-KY」等後綴後比對
    short_name = re.sub(r"-KY$|生技$|生醫$|新藥$|醫藥$|科技$", "", company_name)
    if len(short_name) >= 2 and short_name in title:
        # 額外保護：避免短名稱誤匹配（如「鼎晉」「浩鼎」）
        return company_name in title or company_code in title
    return False


def shorten_title(t: str, max_len: int = 60) -> str:
    """裁短新聞標題作為 highlightReason"""
    t = re.sub(r"\s*-\s*[^-]+$", "", t)  # 移除尾端來源
    if len(t) <= max_len:
        return t
    return t[:max_len].rstrip("。，,. ") + "…"


def main():
    dry_run = "--dry-run" in sys.argv
    today = datetime.now(TAIPEI_TZ)
    today_full = today.strftime("%Y/%m/%d")
    today_iso = today.strftime("%Y-%m-%d")

    print("=" * 60)
    print(" ⭐ 自動標記「本週值得注意」")
    print(f" 執行時間：{today_full} (UTC+8)")
    if dry_run:
        print(" 模式：DRY-RUN（不寫檔）")
    print("=" * 60)

    with open(DATE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    with open(NEWS_PATH, "r", encoding="utf-8") as f:
        news_data = json.load(f)

    code_to_company = {}
    for sec in data:
        for c in sec["companies"]:
            code_to_company[c["code"]] = c

    marked = []          # 本次新標記
    cleared = []         # 本次清除的舊自動標記
    skipped_manual = []  # 因人工標記跳過

    for code, company in code_to_company.items():
        company_news = news_data.get("companies", {}).get(code, {}).get("news", [])
        events = company["events"]

        # === 1. 找出該公司是否有「人工」highlight 標記 ===
        has_manual_highlight = False
        for q, ev in events.items():
            if ev and ev.get("highlightThisWeek") and not ev.get("_autoSource"):
                has_manual_highlight = True
                skipped_manual.append((code, company["name"], q.upper()))
                break

        # === 2. 找出最高分新聞 ===
        best_news = None
        best_score = 0
        best_keywords = []
        for n in company_news:
            title = n.get("title", "")
            if not title_relevant(title, company["name"], code):
                continue
            s, kws = score_news(title)
            if s > best_score:
                best_score = s
                best_news = n
                best_keywords = kws

        if has_manual_highlight:
            # 有人工標記時，仍然要清除其他事件的舊自動標記
            for q, ev in events.items():
                if ev and ev.get("_autoSource") and not ev.get("highlightThisWeek"):
                    # 殘留欄位也清掉
                    ev.pop("_autoSource", None)
            continue

        # === 3. 決定是否標記 ===
        if best_score >= STRONG_THRESHOLD and best_news:
            match = match_event(best_news["title"], events, company)
            if match:
                q, ev, conf = match

                # 先清除該公司所有舊的自動標記
                for qq, ee in events.items():
                    if ee and ee.get("_autoSource"):
                        ee.pop("highlightThisWeek", None)
                        ee.pop("highlightReason", None)
                        ee.pop("_autoSource", None)

                # 套用新標記
                short = shorten_title(best_news["title"])
                ev["highlightThisWeek"] = True
                ev["highlightReason"] = f"{best_news['date']} 新聞：{short}"
                ev["lastConfirmed"] = today_full
                ev["_autoSource"] = f"news_scan_{today_iso}"

                # 「核准」類同步更新 status
                approval_hits = [k for k in best_keywords if k in
                                 ("獲核准", "核准函", "藥證核准", "獲藥證", "獲首張",
                                  "通過上市", "上市核准")]
                resolve_hits = [k for k in best_keywords if k in
                                ("解盲成功", "達主要終點", "療效通過", "期中分析通過",
                                 "IDMC通過", "解盲達標")]
                negative_hits = [k for k in best_keywords if k in
                                 ("失敗", "未達標", "未達主要終點", "解盲未達",
                                  "解盲失敗", "退回", "駁回")]
                if approval_hits:
                    ev["status"] = "已核准"
                    ev["statusLabel"] = "已公布"
                elif resolve_hits:
                    ev["statusLabel"] = "已公布"
                elif negative_hits:
                    ev["statusLabel"] = "延後待確認"

                marked.append({
                    "code": code, "name": company["name"], "quarter": q.upper(),
                    "score": best_score, "keywords": best_keywords[:3],
                    "title": short, "conf": conf,
                })
        else:
            # 沒強催化 → 清除舊的自動標記
            for q, ev in events.items():
                if ev and ev.get("_autoSource"):
                    ev.pop("highlightThisWeek", None)
                    ev.pop("highlightReason", None)
                    ev.pop("_autoSource", None)
                    cleared.append((code, company["name"], q.upper()))

    # === 輸出摘要 ===
    print(f"\n⭐ 自動標記（{len(marked)} 家）")
    print("-" * 60)
    if marked:
        for m in marked:
            kws = ", ".join(m["keywords"]) if m["keywords"] else "-"
            print(f"  [{m['code']}] {m['name']:<10} {m['quarter']} | 分數 {m['score']:>3} | 關鍵字: {kws}")
            print(f"           → {m['title']}")
    else:
        print("  （無）")

    print(f"\n⚪ 清除舊自動標記（{len(cleared)} 個）")
    if cleared:
        for c in cleared:
            print(f"  [{c[0]}] {c[1]} {c[2]}")
    else:
        print("  （無）")

    if skipped_manual:
        print(f"\n🔒 保留人工標記（{len(skipped_manual)} 家，腳本不動）")
        for s in skipped_manual:
            print(f"  [{s[0]}] {s[1]} {s[2]}")

    print(f"\n{'='*60}")

    if dry_run:
        print(" [DRY-RUN] 未寫入檔案。")
    else:
        with open(DATE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        print(f" ✅ 已寫入 {DATE_PATH}")

        # 更新狀態
        try:
            from _status_helper import update_status
            update_status("highlights")
        except Exception:
            pass

    print("=" * 60)


if __name__ == "__main__":
    main()
