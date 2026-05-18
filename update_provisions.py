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


def get_clinical_phase(label):
    """從事件 label 判斷臨床期別，回傳 phase key。
    支援阿拉伯數字（2a/2b）、中文（二期）、英文（Phase 2）、羅馬數字（IIa/IIb/III）。
    回傳值：'phase1', 'phase1b', 'phase2a', 'phase2', 'phase2b', 'phase3', 'interim', 'approval', 'unknown'
    """
    if not label:
        return 'unknown'
    import re
    L = label.lower()
    # 先檢查里程碑類
    if "藥證" in label or "approval" in L: return 'approval'
    if "期中分析" in label or "interim" in L: return 'interim'

    # 阿拉伯數字
    if "3期" in label or "三期" in label or "phase 3" in L: return 'phase3'
    if "2b" in L: return 'phase2b'
    if "2a" in L: return 'phase2a'
    if "2期" in label or "二期" in label or "phase 2" in L: return 'phase2'
    if "1b" in L: return 'phase1b'
    if "1期" in label or "一期" in label or "phase 1" in L: return 'phase1'

    # 羅馬數字（需搭配「期」字或詞尾以避免誤抓 ID 等英文）
    # 順序：III → IIa → IIb → II → Ib → I （長字優先）
    # Python regex \b 對中文邊界判斷不正確，改用具體字串匹配
    if any(p in label for p in ['III期', 'III 期', 'Ⅲ期']) or 'phase iii' in L: return 'phase3'
    if any(p in label for p in ['IIa期', 'IIa 期', 'Ⅱa期', 'iia期']) or 'iia' in L and '期' in label: return 'phase2a'
    if any(p in label for p in ['IIb期', 'IIb 期', 'Ⅱb期', 'iib期']) or 'iib' in L and '期' in label: return 'phase2b'
    if any(p in label for p in ['II期', 'II 期', 'Ⅱ期']) or 'phase ii' in L: return 'phase2'
    if any(p in label for p in ['Ib期', 'Ib 期', 'ib期']): return 'phase1b'
    if any(p in label for p in ['I期', 'I 期', 'Ⅰ期']) or 'phase i' in L: return 'phase1'

    return 'unknown'


# 細胞療法/CAR-T 偵測：高難度技術 + 製程複雜，失敗風險加成
CELL_THERAPY_KEYWORDS = ['cart', 'car-t', 'car t', '幹細胞', '細胞療法', 'cell therapy',
                          'stem cell', 'autologous', 'ipsc', '免疫細胞']

def get_cell_therapy_risk(company, event):
    """細胞療法風險分級
    - 'high_allo'      : 異體 CAR-T / 異體幹細胞（全球無成功上市，極高風險）
    - 'standard_cart'  : 自體 CAR-T / 一般細胞療法（標靶已驗證 e.g., CD19, 風險中等）
    - 'none'           : 非細胞療法
    """
    text = (str(company.get('target', '')) + ' ' +
            str(company.get('indication', '')) + ' ' +
            str(event.get('label', '')) + ' ' +
            str(event.get('detail', '')) + ' ' +
            str(event.get('drug', ''))).lower()

    is_allo = any(k in text for k in ['異體', 'allogeneic', 'allo-car', 'allo car'])
    is_cart_or_stem = any(k in text for k in
        ['cart', 'car-t', 'car t', '幹細胞', '細胞療法', 'stem cell', 'cell therapy', 'autologous'])

    # strategy='cart' 也算
    if company.get('strategy') == 'cart':
        is_cart_or_stem = True

    if is_allo and is_cart_or_stem:
        return 'high_allo'  # 異體 CAR-T / 異體細胞療法 = 全球無上市，極高風險
    if is_allo:
        return 'high_allo'  # 異體幹細胞等
    if is_cart_or_stem:
        return 'standard_cart'  # 自體 CAR-T / 一般細胞療法
    return 'none'


def is_cell_therapy(company, event):
    """是否為任何形式的細胞療法（保留向後相容）"""
    return get_cell_therapy_risk(company, event) != 'none'


# 臨床期別「成功機率」基礎分（糧草先行視角：早期解盲幾乎都過）
# 來源：Hay et al. (2014) BIO Industry Analysis 臨床試驗成功率統計
PHASE_SUCCESS_BASE = {
    'phase1':   92,  # 安全性試驗，幾乎都過
    'phase1b':  88,  # dose-finding，多數能達主要終點
    'phase2a':  72,  # POC 試驗，有療效訊號就過
    'phase2':   65,
    'phase2b':  52,  # 樞紐前驗證，已開始有失敗風險
    'phase3':   42,  # 樞紐試驗，~60% 失敗率
    'interim':  78,  # 期中分析通過 = 已有正面訊號
    'approval': 85,  # 申請藥證 = 已過 3 期
    'unknown':  60,
}


def score_clinical(event, company=None):
    """🧬 臨床訊號：收案進度 + 催化強度 + 期別風險平衡
    糧草先行視角：早期 = 低風險、晚期 = 高風險高 reward
    細胞療法（CAR-T/幹細胞）製程複雜、臨床達標難度高，扣分
    """
    score = 40  # 基礎

    # 已公布實績（最強訊號，里程碑代表 derisking）
    # 改：同時掃 announcedNote / statusLabel / detail，三者任一含里程碑關鍵字皆算
    ann_text = (event.get("announcedNote") or "")
    status_text = (event.get("statusLabel") or "") + " " + (event.get("status") or "")
    detail_text = (event.get("detail") or "")
    combined_milestone = ann_text + " " + status_text + " " + detail_text

    has_announced = bool(ann_text)
    # 偵測里程碑關鍵字
    MILESTONE_STRONG = ["收案完成", "期中分析通過", "IDMC", "達標", "已進入審查", "DSMB"]
    MILESTONE_RESOLVED = ["解盲", "讀出"]
    has_strong = any(k in combined_milestone for k in MILESTONE_STRONG)
    has_resolved = any(k in combined_milestone for k in MILESTONE_RESOLVED)

    if has_strong:
        score += 35  # 重大里程碑：執行力強 + 時程確定 + 風險降低
    elif has_resolved:
        score += 28
    elif has_announced:
        score += 15

    # 額外：收案超前 / 提前完成 = 加碼
    if any(k in combined_milestone for k in ["超前", "提前", "比預期", "超過預期", "比原訂"]):
        score += 8
    # 額外：詳細日期（YYYY/MM/DD 完成）= 公司公開透明
    import re
    if re.search(r'\d{4}/\d{2}/\d{2}', ann_text):
        score += 3

    # 大規模收案階梯加分（罕病門檻較低，因人數本來就少）
    # 從 detail / ann 抓最大的「N 人/位」數字
    nums = [int(x) for x in re.findall(r'(\d{2,5})\s*[人位]', combined_milestone)]
    if nums:
        n = max(nums)
        if n >= 1000:   score += 10
        elif n >= 800:  score += 8
        elif n >= 500:  score += 6
        elif n >= 300:  score += 4
        elif n >= 100:  score += 3
        elif n >= 50:   score += 2  # 罕病常見規模

    # 催化強度
    cl = event.get("catalystLevel", "")
    score += {"高": 15, "中高": 10, "中": 5, "中低": 2, "低": 0}.get(cl, 0)

    # 期別調整（糧草先行視角）：
    # - 早期解盲（1/1b）穩定，加分
    # - 中期（2/2a）平衡，小幅加分
    # - 晚期（2b/3）高風險，扣分
    phase = get_clinical_phase(event.get("label", ""))
    phase_adj = {
        'phase1':   +10,   # 安全性試驗
        'phase1b':  +8,    # 幾乎一定過
        'phase2a':  +3,
        'phase2':   0,
        'phase2b':  -3,    # 開始有失敗風險
        'phase3':   -8,    # 高風險，但若過了 reward 大
        'interim':  +5,    # 期中通過 = 已減半風險
        'approval': +12,   # 申請藥證 = 最穩
        'unknown':  0,
    }
    score += phase_adj.get(phase, 0)

    # 投資亮點數量（公司資訊豐富 = 投資人能看清楚）
    bf = event.get("bonusFactors", [])
    if bf: score += min(8, len(bf))

    # 細胞療法分級扣分
    if company:
        risk = get_cell_therapy_risk(company, event)
        if risk == 'high_allo':
            score -= 18  # 異體 CAR-T / 幹細胞 - 全球無上市，極高失敗風險
        elif risk == 'standard_cart':
            score -= 5   # 自體 CAR-T / 一般細胞療法 - 已有驗證標靶

    return max(10, min(100, score))


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


def score_share_structure(total_s, market=None):
    """📦 籌碼結構：股本越小越易拉抬（生技股投資邏輯）
    台股 1 股面額 10 元，股本 = total_s × 10。
    上市公司（market=listed）有 10% 漲跌幅限制，較難快速拉抬，扣分。
    """
    if not total_s or total_s <= 0:
        base = 50  # 資料缺失，中性
    elif total_s < 5e7:      base = 100  # < 5千萬股（極小型）
    elif total_s < 1e8:      base = 90   # 5千萬~1億股（小型）
    elif total_s < 1.5e8:    base = 78   # 1~1.5億股（中小型）
    elif total_s < 2.5e8:    base = 60   # 1.5~2.5億股（中型）
    elif total_s < 4e8:      base = 42   # 2.5~4億股（中大型）
    elif total_s < 6e8:      base = 28   # 4~6億股（大型）
    else:                    base = 15   # > 6億股（巨型）

    # 上市（TWSE）有 10% 漲跌幅 + 較嚴監管 → 拉抬難度高
    if market == 'listed':
        base = max(5, base - 20)

    return base


def score_success_prob_with_penalty(scores_entry, event, company=None):
    """📊 成功機率 (含細胞療法分級懲罰)
    異體 CAR-T 全球無成功上市，懲罰最重
    """
    base = score_success_prob(scores_entry, event)
    if company:
        risk = get_cell_therapy_risk(company, event)
        if risk == 'high_allo':
            base = max(10, base - 15)  # 異體 = 全球未驗證，達標機率極低
        elif risk == 'standard_cart':
            base = max(10, base - 4)   # 自體 = 已有同類藥上市，風險可控
    return base


def score_success_prob(scores_entry, event):
    """📊 成功機率：以臨床期別歷史成功率為基礎
    糧草先行視角：早期解盲機率高、晚期低
    """
    phase = get_clinical_phase(event.get("label", ""))
    base = PHASE_SUCCESS_BASE.get(phase, 60)

    # 已公布實績（IDMC 通過 / 期中通過 / 收案完成 / DSMB 通過）= 成功機率大增
    # 改：同時掃 announcedNote / statusLabel / detail
    ann_text = event.get("announcedNote", "") or ""
    status_text = (event.get("statusLabel") or "") + " " + (event.get("status") or "")
    detail_text = event.get("detail", "") or ""
    combined = ann_text + " " + status_text + " " + detail_text

    if any(k in combined for k in ["IDMC", "期中分析通過", "達標", "DSMB"]):
        base = min(100, base + 18)
    elif any(k in combined for k in ["收案完成", "收案超前", "已進入審查"]):
        base = min(100, base + 14)
    # 超前 / 提前完成額外加碼
    if any(k in combined for k in ["超前", "提前", "比預期", "比原訂"]):
        base = min(100, base + 8)
    # 大規模收案加碼
    import re
    nums = [int(x) for x in re.findall(r'(\d{2,5})\s*[人位]', combined)]
    if nums:
        n = max(nums)
        if n >= 1000:   base = min(100, base + 8)
        elif n >= 800:  base = min(100, base + 6)
        elif n >= 500:  base = min(100, base + 4)
        elif n >= 300:  base = min(100, base + 2)
        elif n >= 50:   base = min(100, base + 1)  # 罕病小規模也加

    # 公司既有臨床可信度也納入（次要）
    if scores_entry:
        cc = scores_entry.get("components", {}).get("clinicalCredibility", 50)
        # 30% 來自公司既有可信度，70% 來自期別基礎機率
        base = round(base * 0.7 + cc * 0.3, 1)

    return min(100, base)


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

    # 讀 holders.json 取 total_s 計算股本
    holders_path = os.path.join(HERE, "holders.json")
    try:
        with open(holders_path, "r", encoding="utf-8") as f:
            h_data = json.load(f).get("data", [])
        share_map = {c.get("code"): c.get("total_s") for c in h_data}
    except Exception:
        share_map = {}

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

            # 算 7 個維度分數
            imm = score_imminence(days_until)
            pw_result = score_price_window(c.get("priceHistory", []))
            if isinstance(pw_result, tuple):
                pw, percentile, vol_pct = pw_result
            else:
                pw, percentile, vol_pct = pw_result, None, None
            cl = score_clinical(event, company=c)
            cs = score_cash(cf_data.get(code, {}))
            ns = score_news(news_data.get(code), event)
            sp = score_success_prob_with_penalty(scores_data.get(code), event, company=c)
            total_s = share_map.get(code, 0)
            ss = score_share_structure(total_s, market=c.get("market"))
            is_ct = is_cell_therapy(c, event)
            is_listed = (c.get("market") == "listed")

            # 加權總分（7 維度）
            total = round(
                imm * 0.25 +
                pw  * 0.17 +
                cl  * 0.18 +
                cs  * 0.09 +
                ns  * 0.09 +
                sp  * 0.10 +
                ss  * 0.12,
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

            # 上市公司拉抬難度標籤
            if is_listed:
                advice.append("上市拉抬難")
            # 細胞療法分級標籤
            ct_risk = get_cell_therapy_risk(c, event)
            if ct_risk == 'high_allo':
                advice.append("異體細胞療法(極高風險)")
            elif ct_risk == 'standard_cart':
                advice.append("自體CAR-T(標靶已驗證)")

            # 風險等級（依期別）
            phase = get_clinical_phase(event.get("label", ""))
            risk_label = {
                'phase1':   "低風險解盲(1期)",
                'phase1b':  "低風險解盲(1b)",
                'phase2a':  "中風險解盲(2a)",
                'phase2':   "中風險解盲(2期)",
                'phase2b':  "中高風險(2b)",
                'phase3':   "高風險解盲(3期)",
                'interim':  "期中通過(已降風險)",
                'approval': "藥證審查(低風險)",
                'unknown':  None,
            }.get(phase)
            if risk_label:
                advice.append(risk_label)

            # 5 日股價歷史（給卡片顯示）
            ph = c.get("priceHistory") or []
            ph_last5 = ph[-5:] if len(ph) >= 5 else ph

            # 股本標籤
            share_label = None
            share_short = None
            if total_s:
                if total_s < 5e7:    share_label, share_short = ("極小型(易拉抬)", f"{total_s/1e7:.1f}千萬股")
                elif total_s < 1e8:  share_label, share_short = ("小型(易拉抬)", f"{total_s/1e7:.1f}千萬股")
                elif total_s < 1.5e8: share_label, share_short = ("中小型", f"{total_s/1e8:.2f}億股")
                elif total_s < 2.5e8: share_label, share_short = ("中型", f"{total_s/1e8:.2f}億股")
                elif total_s < 4e8:  share_label, share_short = ("中大型(較難)", f"{total_s/1e8:.2f}億股")
                elif total_s < 6e8:  share_label, share_short = ("大型(難拉抬)", f"{total_s/1e8:.2f}億股")
                else:                share_label, share_short = ("巨型(難拉抬)", f"{total_s/1e8:.2f}億股")

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
                    "shareStructure": round(ss, 1),
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
                    "history5d": ph_last5,
                    "current": (ph_last5[-1]["close"] if ph_last5 else None),
                },
                "shareCapital": {
                    "totalShares": total_s,
                    "label": share_label,
                    "short": share_short,
                },
                "flags": {
                    "isListed": is_listed,
                    "isCellTherapy": is_ct,
                    "cellTherapyRisk": get_cell_therapy_risk(c, event),  # 'high_allo' / 'standard_cart' / 'none'
                },
                "advice": " · ".join(advice) if advice else "—",
            })

    # 依總分排序
    results.sort(key=lambda r: -r["provisionScore"])

    # 輸出 TOP 10（前端只顯示 TOP N，但我們存全部）
    print(f"\n找到 {len(results)} 家有解盲類事件的公司，TOP 10：")
    print(f"{'排名':<4} {'代號':<6} {'公司':<12} {'糧草分':<7} {'迫近':<5} {'股價':<5} {'臨床':<5} {'現金':<5} {'新聞':<5} {'機率':<5} {'籌碼':<5}")
    print("-" * 96)
    for i, r in enumerate(results[:10], 1):
        co = r["components"]
        sc = r.get("shareCapital", {})
        print(f"{i:<4} {r['code']:<6} {r['name']:<12} {r['provisionScore']:<7} "
              f"{co['imminence']:<5} {co['priceWindow']:<5} {co['clinical']:<5} "
              f"{co['cash']:<5} {co['newsHeat']:<5} {co['successProb']:<5} {co.get('shareStructure',0):<5}")
        print(f"      ↳ {r['event']['quarter']} {r['event']['drug'] or '-'} «{r['event']['label']}» "
              f"({r['advice']}) | 股本: {sc.get('short','?')}")

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
