# -*- coding: utf-8 -*-
"""
update_cashflow.py - 抓取 25 家公司的現金流資料

策略：
- 上市公司 (.TW)：用 yfinance 自動抓取（年度 + 季度）
- 興櫃公司 (.TWO)：Yahoo 沒資料；保留欄位，可手動編輯 cashflow.json 補資料
- 優先顯示 2026 Q1 等最新季度，沒有就用 2025 年報

寫入：cashflow.json
"""
import json, sys, os, time, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

TAIPEI_TZ = timezone(timedelta(hours=8))
DATE_PATH = os.path.join(os.path.dirname(__file__), "date.json")
CF_PATH = os.path.join(os.path.dirname(__file__), "cashflow.json")


# ── 來源1：FinMind 開放 API（主來源，覆蓋 2026 Q1）─────────────
def fetch_finmind(code):
    """
    從 FinMind 抓 2023-2026 各季度現金及約當現金（每年取最新一季）。
    回傳：{cash_2023, cash_2024, cash_2025, cash_2026, source}  或  None
    """
    url = 'https://api.finmindtrade.com/api/v4/data'
    params = {
        'dataset': 'TaiwanStockBalanceSheet',
        'data_id': code,
        'start_date': '2023-01-01',
        'end_date': '2026-12-31',
    }
    full_url = url + '?' + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(full_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=20) as r:
            resp = json.loads(r.read().decode('utf-8'))
        if resp.get('status') != 200:
            return None
        items = resp.get('data', [])
    except Exception:
        return None

    # 篩出「現金及約當現金」，依日期分組（每年取最新一季）
    by_year = {}
    for it in items:
        if it.get('type') != 'CashAndCashEquivalents':
            continue
        d = it.get('date', '')   # 'YYYY-MM-DD'
        v = it.get('value')
        if not d or v is None:
            continue
        yr = d[:4]
        if yr not in by_year or d > by_year[yr][0]:
            by_year[yr] = (d, v)

    if not by_year:
        return None

    def make_entry(yr_key):
        if yr_key not in by_year:
            return None
        d, v = by_year[yr_key]
        mo = int(d[5:7])
        q = (mo - 1) // 3 + 1
        period = f'{yr_key}年底' if mo == 12 else f'{yr_key} Q{q}底'
        return {'period': period, 'value': float(v)}

    result = {
        'cf_2025': None,
        'cf_2026': None,
        'cash_2023': make_entry('2023'),
        'cash_2024': make_entry('2024'),
        'cash_2025': make_entry('2025'),
        'cash_2026': make_entry('2026'),
        'source': 'finmind',
    }
    if any(v for k, v in result.items() if k.startswith('cash_')):
        return result
    return None


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
        "source": "FinMind (主, 含 2026 Q1) + yfinance (備援) + 手動 (興櫃)",
        "companies": {},
    }

    auto_ok = 0
    finmind_ok = 0
    yf_ok = 0
    manual_kept = 0
    no_data = []

    for code, name, market in companies:
        print(f"\n  [{code}] {name}...", end=" ", flush=True)

        # 1. 先試 FinMind (覆蓋 2026 Q1 + 上市櫃 + 部分興櫃)
        cf_fm = fetch_finmind(code)
        time.sleep(0.4)

        # 2. 再試 yfinance (上市備援；補 operating_cf)
        cf_yf = None
        if market == "listed":
            cf_yf = fetch_yf(code)
            time.sleep(0.3)

        existing_entry = existing.get(code, {})
        # 合併三來源：FinMind 主，yfinance 補 operating_cf，existing 補殘缺
        cf = None
        if cf_fm or cf_yf:
            cf = {
                "cf_2025": None,
                "cf_2026": None,
                "cash_2023": None,
                "cash_2024": None,
                "cash_2025": None,
                "cash_2026": None,
                "source": "",
                "suffix": (cf_yf or {}).get("suffix", ""),
            }
            sources = []
            # FinMind 為主 (cash_*)
            if cf_fm:
                for fld in ("cash_2023", "cash_2024", "cash_2025", "cash_2026"):
                    if (cf_fm.get(fld) or {}).get("value"):
                        cf[fld] = cf_fm[fld]
                sources.append("finmind")
                finmind_ok += 1
            # yfinance 補：operating_cf 和 FinMind 缺的欄位
            if cf_yf:
                if (cf_yf.get("cf_2025") or {}).get("operating_cf"):
                    cf["cf_2025"] = cf_yf["cf_2025"]
                if (cf_yf.get("cf_2026") or {}).get("operating_cf"):
                    cf["cf_2026"] = cf_yf["cf_2026"]
                for fld in ("cash_2023", "cash_2024", "cash_2025", "cash_2026"):
                    if not (cf.get(fld) or {}).get("value") and (cf_yf.get(fld) or {}).get("value"):
                        cf[fld] = cf_yf[fld]
                if "yfinance" not in sources:
                    sources.append("yfinance")
                    yf_ok += 1
            cf["source"] = "+".join(sources)

        if cf:
            # 補：FinMind/yf 都沒抓到的，用 existing (手動 Goodinfo) 填補
            merged = dict(cf)
            for fld in ("cash_2023", "cash_2024", "cash_2025", "cash_2026"):
                if not (merged.get(fld) or {}).get("value") and (existing_entry.get(fld) or {}).get("value"):
                    merged[fld] = existing_entry[fld]
                    if "goodinfo" not in merged["source"]:
                        merged["source"] = merged["source"] + "+goodinfo"
            result["companies"][code] = merged
            ca25 = (merged.get("cash_2025") or {}).get("value")
            ca26 = (merged.get("cash_2026") or {}).get("value")
            s25 = f"{ca25/1e8:.2f}億" if ca25 else "—"
            s26 = f"{ca26/1e8:.2f}億" if ca26 else "—"
            print(f"✅ [{merged['source']}] 2025={s25} 2026={s26}")
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
    print(f" ✅ 自動抓到：{auto_ok}/{len(companies)}（FinMind:{finmind_ok} / yfinance:{yf_ok}）")
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
