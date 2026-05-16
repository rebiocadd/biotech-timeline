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


def fetch_yf(code):
    """用 yfinance 抓現金流 + 現金部位（僅上市有效）"""
    try:
        import yfinance as yf
    except ImportError:
        return None

    for suffix in ('.TW', '.TWO'):
        try:
            t = yf.Ticker(f"{code}{suffix}")
            q_cf = t.quarterly_cashflow
            y_cf = t.cashflow

            chosen_series = None
            period = None
            ptype = None

            # 優先用季度資料
            if q_cf is not None and not q_cf.empty:
                latest_col = q_cf.columns[0]
                chosen_series = q_cf[latest_col]
                period = quarter_label(latest_col.to_pydatetime() if hasattr(latest_col, 'to_pydatetime') else None)
                ptype = "Q"
            elif y_cf is not None and not y_cf.empty:
                latest_col = y_cf.columns[0]
                chosen_series = y_cf[latest_col]
                period = annual_label(latest_col.to_pydatetime() if hasattr(latest_col, 'to_pydatetime') else None)
                ptype = "Y"
            else:
                continue

            # OCF
            ocf = None
            for k in ('Operating Cash Flow', 'Total Cash From Operating Activities',
                      'Cash Flow From Continuing Operating Activities'):
                if k in chosen_series.index:
                    v = chosen_series[k]
                    if v is not None and not (isinstance(v, float) and (v != v)):  # NaN check
                        ocf = float(v)
                        break

            # 現金部位（從 balance sheet）
            cash = None
            try:
                bs = t.quarterly_balance_sheet
                if bs is not None and not bs.empty:
                    bcol = bs.columns[0]
                    for k in ('Cash And Cash Equivalents', 'Cash', 'Cash Cash Equivalents And Short Term Investments'):
                        if k in bs.index:
                            v = bs.loc[k, bcol]
                            if v is not None and not (isinstance(v, float) and (v != v)):
                                cash = float(v)
                                break
            except Exception:
                pass

            return {
                "period": period,
                "type": ptype,
                "operating_cf": ocf,
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
            ocf_str = f"{cf['operating_cf']/1e8:.2f}億" if cf['operating_cf'] else "N/A"
            print(f"✅ 自動 {cf['period']} OCF={ocf_str}")
            auto_ok += 1
        elif code in existing and existing[code].get("operating_cf") is not None:
            # 保留現有手動資料
            result["companies"][code] = existing[code]
            print(f"📝 沿用手動: {existing[code].get('period', '?')}")
            manual_kept += 1
        else:
            # 無資料
            result["companies"][code] = {
                "period": None,
                "type": None,
                "operating_cf": None,
                "cash_position": None,
                "source": "manual_pending",
                "note": "可手動編輯 cashflow.json 補資料",
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
