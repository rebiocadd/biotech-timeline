#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日藥祇(7878)早報 → Telegram。

由 GitHub Actions 於 06:00 TST 執行。需在 repo 設定 Secrets：
  TELEGRAM_TOKEN    你的 bot token（BotFather 給的）
  TELEGRAM_CHAT_ID  收訊的 chat id（你和 bot 對話的 id）

本機測試（不發送、只印出訊息）：python send_telegram.py --dry
"""
import json, os, sys
import urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from send_email import load, find_company, CODE, SITE

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

TZ = timezone(timedelta(hours=8))


def esc(s):
    return str(s if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_text():
    d = load("date.json"); ns = load("news_status.json"); sc = load("scores.json")
    c = find_company(d, CODE) or {}
    name = c.get("name", "藥祇生醫"); price = c.get("price", "—"); change = c.get("change", "")
    pdate = c.get("priceDate", ""); wave = (c.get("wave10") or [])[-5:]
    news = (((ns or {}).get("companies") or {}).get(CODE, {}) or {}).get("news", [])[:5]
    score = ((sc or {}).get("companies") or {}).get(CODE, {}) or {}
    now = datetime.now(TZ)
    try:
        chg = float(change)
    except Exception:
        chg = 0.0
    arrow = "🔺" if chg > 0 else ("🔻" if chg < 0 else "▪️")
    waveline = " → ".join(str(w.get("close")) for w in wave)

    L = []
    L.append(f"📡 <b>台灣生技雷達 · {esc(name)} {CODE} 早報</b>")
    L.append(f"<i>{now.strftime('%Y/%m/%d')}（週{'一二三四五六日'[now.weekday()]}）</i>")
    L.append("")
    L.append(f"💰 <b>收盤 {esc(price)}</b> {arrow}{esc(change)}%  <i>（截至 {esc(pdate)}）</i>")
    if waveline:
        L.append(f"　近5日: {esc(waveline)}")
    L.append(f"🎯 AI 評分 <b>{esc(score.get('total', '—'))}</b> {esc((score.get('band') or {}).get('label', ''))}")
    evs = [(q, ev) for q, ev in (c.get("events") or {}).items() if ev]
    if evs:
        L.append("")
        L.append("🔬 <b>2026 臨床事件</b>")
        for q, ev in evs:
            st = ev.get("statusLabel") or ev.get("eventIndication") or "-"
            L.append(f"• {q.upper()} {esc(ev.get('drug', ''))} {esc(ev.get('label', ''))}（{esc(st)}）")
    if news:
        L.append("")
        L.append("📰 <b>最新消息</b>")
        for n in news:
            t = (n.get("title") or "").rsplit(" - ", 1)[0]
            L.append(f"• {esc(n.get('date', ''))} {esc(t)}")
    L.append("")
    L.append(f'<a href="{SITE}">📈 開啟完整雷達</a> · 僅供研究、非投資建議')
    return "\n".join(L)


def main():
    text = build_text()
    if "--dry" in sys.argv:
        print(text); return
    token = os.environ.get("TELEGRAM_TOKEN"); chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("跳過 Telegram（未設定 TELEGRAM_TOKEN / TELEGRAM_CHAT_ID）"); return
    data = urllib.parse.urlencode({
        "chat_id": chat, "text": text,
        "parse_mode": "HTML", "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            resp = json.loads(r.read().decode())
        print("✅ Telegram 已送出" if resp.get("ok") else f"❌ Telegram 失敗：{resp}")
        if not resp.get("ok"):
            sys.exit(1)
    except Exception as e:
        print(f"❌ Telegram 送出錯誤：{e}"); sys.exit(1)


if __name__ == "__main__":
    main()
