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

            # 現金餘額（2023/2024/2025 年底 + 2026 最新季）
            cash_2023 = None
            cash_2024 = None
            cash_2025 = None
            cash_2026 = None
            cash_keys = ('Cash And Cash Equivalents', 'Cash',
                         'Cash Cash Equivalents And Short Term Investments')

            def _extract_cash_from_col(df, col):
                for k in cash_keys:
                    if k in df.index:
                        v = df.loc[k, col]
                        try:
                            v = float(v)
                            if v == v:
                                return v
                        except Exception:
                            pass
                return None

            try:
                # 年度 balance sheet → 取 2023/2024/2025 年底
                y_bs = t.balance_sheet
                if y_bs is not None and not y_bs.empty:
                    for col in y_bs.columns:
                        if not hasattr(col, 'year'):
                            continue
                        v = _extract_cash_from_col(y_bs, col)
                        if v is None:
                            continue
                        if col.year == 2023 and cash_2023 is None:
                            cash_2023 = {"period": "2023年底", "value": v}
                        elif col.year == 2024 and cash_2024 is None:
                            cash_2024 = {"period": "2024年底", "value": v}
                        elif col.year == 2025 and cash_2025 is None:
                            cash_2025 = {"period": "2025年底", "value": v}

                # 季度 balance sheet
                q_bs = t.quarterly_balance_sheet
                if q_bs is not None and not q_bs.empty:
                    # 2026 最新季
                    qs_2026 = sorted([c for c in q_bs.columns if hasattr(c, 'year') and c.year == 2026], reverse=True)
                    if qs_2026:
                        col = qs_2026[0]
                        v = _extract_cash_from_col(q_bs, col)
                        if v is not None:
                            q_num = (col.month - 1) // 3 + 1
                            cash_2026 = {"period": f"2026 Q{q_num}底", "value": v}
                    # fallback: 若年度找不到，用季度 Q4
                    for yr, slot in [(2023, 'cash_2023'), (2024, 'cash_2024'), (2025, 'cash_2025')]:
                        if locals()[slot] is None:
                            qs_y = sorted([c for c in q_bs.columns if hasattr(c, 'year') and c.year == yr], reverse=True)
                            if qs_y:
                                col = qs_y[0]
                                v = _extract_cash_from_col(q_bs, col)
                                if v is not None:
                                    q_num = (col.month - 1) // 3 + 1
                                    val = {"period": f"{yr} Q{q_num}底", "value": v}
                                    if yr == 2023: cash_2023 = val
                                    elif yr == 2024: cash_2024 = val
                                    elif yr == 2025: cash_2025 = val
            except Exception:
                pass

            if cf_2025 or cf_2026 or cash_2023 or cash_2024 or cash_2025 or cash_2026:
                return {
                    "cf_2025": cf_2025,
                    "cf_2026": cf_2026,
                    "cash_2023": cash_2023,
                    "cash_2024": cash_2024,
                    "cash_2025": cash_2025,
                    "cash_2026": cash_2026,
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

        existing_entry = existing.get(code, {})
        if cf:
            # 合併策略：yfinance 為主，但保留現有 Goodinfo cash_* 若 yfinance 沒抓到
            merged = dict(cf)
            # 確保 4 個年度欄位都存在
            for fld in ("cash_2023", "cash_2024", "cash_2025", "cash_2026"):
                if not (merged.get(fld) or {}).get("value") and (existing_entry.get(fld) or {}).get("value"):
                    merged[fld] = existing_entry[fld]
                if fld not in merged:
                    merged[fld] = None
            # 標註多元來源
            if (existing_entry.get("cash_2025") or {}).get("period") and not (cf.get("cash_2025") or {}).get("value"):
                merged["source"] = "yfinance+goodinfo"
            result["companies"][code] = merged
            ca25 = (merged.get("cash_2025") or {}).get("value")
            ca26 = (merged.get("cash_2026") or {}).get("value")
            s25 = f"{ca25/1e8:.2f}億" if ca25 else "—"
            s26 = f"{ca26/1e8:.2f}億" if ca26 else "—"
            print(f"✅ 2025現金={s25} 2026現金={s26}")
            auto_ok += 1
        elif (existing_entry.get("cf_2025") or existing_entry.get("cf_2026")
              or existing_entry.get("cash_2023") or existing_entry.get("cash_2024")
              or existing_entry.get("cash_2025") or existing_entry.get("cash_2026")):
            # 沿用既有手動/Goodinfo 資料，補齊缺欄
            entry = dict(existing_entry)
            for fld in ("cash_2023", "cash_2024", "cash_2025", "cash_2026"):
                if fld not in entry:
                    entry[fld] = None
            result["companies"][code] = entry
            ca25 = (entry.get("cash_2025") or {}).get("value")
            s25 = f"{ca25/1e8:.2f}億" if ca25 else "?"
            print(f"📝 沿用既有資料 (cash_2025={s25})")
            manual_kept += 1
        else:
            result["companies"][code] = {
                "cf_2025": None,
                "cf_2026": None,
                "cash_2023": None,
                "cash_2024": None,
                "cash_2025": None,
                "cash_2026": None,
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
