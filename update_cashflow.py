# -*- coding: utf-8 -*-
"""
update_cashflow.py - 抓取 25 家公司的現金流資料

策略：
- 上市公司 (.TW)：用 yfinance 自動抓取（年度 + 季度）
- 興櫃公司 (.TWO)：Yahoo 沒資料；保留欄位，可手動編輯 cashflow.json 補資料
- 優先顯示 2026 Q1 等最新季度，沒有就用 2025 年報

寫入：cashflow.json
"""
import json, sys, os, time
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

TAIPEI_TZ = timezone(timedelta(hours=8))
DATE_PATH = os.path.join(os.path.dirname(__file__), "date.json")
CF_PATH = os.path.join(os.path.dirname(__file__), "cashflow.json")


def load_companies():
    with open(DATE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for sec in data:
        for c in sec["companies"]:
            out.append((c["code"], c["name"], c.get("market", "otc")))
    return out


def quarter_label(dt):
    """日期 → '2026 Q1' 等格式"""
    if dt is None:
        return "未知"
    yr = dt.year
    mo = dt.month
    q = (mo - 1) // 3 + 1
    return f"{yr} Q{q}"


def annual_label(dt):
    if dt is None:
        return "未知"
    return f"{dt.year} 年報"


OCF_KEYS = (
    'Operating Cash Flow',
    'Total Cash From Operating Activities',
    'Cash Flow From Continuing Operating Activities',
)


def _extract_ocf(df, col):
    """從 DataFrame 抽出指定欄位的 OCF；找不到回 None"""
    for k in OCF_KEYS:
        if k in df.index:
            v = df.loc[k, col]
            try:
                v = float(v)
                if v == v:  # not NaN
                    return v
            except Exception:
                pass
    return None


def fetch_yf(code):
    """用 yfinance 抓 2025 年報 + 2026 YTD（累計各季）+ 現金部位"""
    try:
        import yfinance as yf
    except ImportError:
        return None

    for suffix in ('.TW', '.TWO'):
        try:
            t = yf.Ticker(f"{code}{suffix}")
            q_cf = t.quarterly_cashflow
            y_cf = t.cashflow

            cf_2025 = None
            cf_2026 = None

            # 2025 年報（從年度資料）
            if y_cf is not None and not y_cf.empty:
                for col in y_cf.columns:
                    if hasattr(col, 'year') and col.year == 2025:
                        ocf = _extract_ocf(y_cf, col)
                        if ocf is not None:
                            cf_2025 = {"period": "2025 年報", "operating_cf": ocf}
                        break

            # 若年報沒有，從季度合計 2025 全年
            if cf_2025 is None and q_cf is not None and not q_cf.empty:
                qs_2025 = [c for c in q_cf.columns if hasattr(c, 'year') and c.year == 2025]
                if qs_2025:
                    total = 0
                    cnt = 0
                    for col in qs_2025:
                        v = _extract_ocf(q_cf, col)
                        if v is not None:
                            total += v
                            cnt += 1
                    if cnt > 0:
                        cf_2025 = {"period": f"2025 (Q1-Q{cnt})", "operating_cf": total}

            # 2026 YTD：累計可得的 2026 季度
            if q_cf is not None and not q_cf.empty:
                qs_2026 = sorted([c for c in q_cf.columns if hasattr(c, 'year') and c.year == 2026])
                if qs_2026:
                    total = 0
                    quarters = []
                    for col in qs_2026:
                        v = _extract_ocf(q_cf, col)
                        if v is not None:
                            total += v
                            q_num = (col.month - 1) // 3 + 1
                            quarters.append(f"Q{q_num}")
                    if quarters:
                        cf_2026 = {
                            "period": f"2026 {'-'.join(quarters) if len(quarters) > 1 else quarters[0]}",
                            "operating_cf": total
                        }

            # 現金部位（最新一季）
            cash = None
            try:
                bs = t.quarterly_balance_sheet
                if bs is not None and not bs.empty:
                    bcol = bs.columns[0]
                    for k in ('Cash And Cash Equivalents', 'Cash',
                              'Cash Cash Equivalents And Short Term Investments'):
                        if k in bs.index:
                            v = bs.loc[k, bcol]
                            try:
                                v = float(v)
                                if v == v:
                                    cash = v
                                    break
                            except Exception:
                                pass
            except Exception:
                pass

            if cf_2025 or cf_2026:
                return {
                    "cf_2025": cf_2025,
                    "cf_2026": cf_2026,
                    "cash_position": cash,
                    "source": "yfinance",
                    "suffix": suffix,
                }
        except Exception:
            continue
    return None


def main():
    now = datetime.now(TAIPEI_TZ)
    print("=" * 60)
    print(" 現金流抓取（yfinance + 手動補）")
    print(f" 執行時間：{now.strftime('%Y/%m/%d %H:%M')} UTC+8")
    print("=" * 60)

    # 讀取現有 cashflow.json（保留手動編輯的興櫃資料）
    existing = {}
    if os.path.exists(CF_PATH):
        try:
            with open(CF_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f).get("companies", {})
        except Exception:
            pass

    companies = load_companies()
    result = {
        "lastRun": now.strftime("%Y/%m/%d %H:%M"),
        "tz": "UTC+8",
        "source": "yfinance (上市) + 手動 (興櫃)",
        "companies": {},
    }

    auto_ok = 0
    manual_kept = 0
    no_data = []

    for code, name, market in companies:
        print(f"\n  [{code}] {name}...", end=" ", flush=True)
        cf = None
        if market == "listed":
            cf = fetch_yf(code)
            time.sleep(0.3)

        if cf:
            result["companies"][code] = cf
            ocf25 = (cf.get("cf_2025") or {}).get("operating_cf")
            ocf26 = (cf.get("cf_2026") or {}).get("operating_cf")
            s25 = f"{ocf25/1e8:.2f}億" if ocf25 else "—"
            s26 = f"{ocf26/1e8:.2f}億" if ocf26 else "—"
            print(f"✅ 2025={s25} 2026={s26}")
            auto_ok += 1
        elif code in existing and (existing[code].get("cf_2025") or existing[code].get("cf_2026")):
            # 沿用手動資料
            result["companies"][code] = existing[code]
            print(f"📝 沿用手動")
            manual_kept += 1
        else:
            result["companies"][code] = {
                "cf_2025": None,
                "cf_2026": None,
                "cash_position": None,
                "source": "manual_pending",
            }
            no_data.append(f"{code} {name}")
            print("⏳ 待補")

    with open(CF_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))

    print("\n" + "=" * 60)
    print(f" ✅ 自動抓到：{auto_ok}/{len(companies)}")
    print(f" 📝 沿用手動：{manual_kept}")
    print(f" ⏳ 待補資料：{len(no_data)}")
    if no_data:
        for n in no_data:
            print(f"    - {n}")
    print(f" 📁 寫入 {CF_PATH}")
    print("=" * 60)

    try:
        from _status_helper import update_status
        update_status("cashflow")
    except Exception:
        pass


if __name__ == "__main__":
    main()
