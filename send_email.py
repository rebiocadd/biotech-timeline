#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日藥祇(7878)早報 email。

由 GitHub Actions 於 06:30 TST 執行。需在 repo 設定以下 Secrets：
  MAIL_USER  寄件 Gmail（例：rebiocadd@gmail.com）
  MAIL_PASS  Gmail「應用程式密碼」16 碼（非登入密碼）
  MAIL_TO    收件信箱（省略則寄給自己）

本機測試（不寄信、只產出預覽 HTML）：python send_email.py --dry
"""
import json, os, sys, smtplib, ssl
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
BASE = os.path.dirname(os.path.abspath(__file__))
CODE = "7878"
SITE = "https://rebiocadd.github.io/biotech-timeline/"


def load(f):
    try:
        with open(os.path.join(BASE, f), encoding="utf-8") as fp:
            return json.load(fp)
    except Exception:
        return None


def find_company(date_json, code):
    for sec in date_json or []:
        for c in sec.get("companies", []):
            if c.get("code") == code:
                return c
    return None


def build():
    d = load("date.json"); ns = load("news_status.json"); sc = load("scores.json")
    c = find_company(d, CODE) or {}
    name = c.get("name", "藥祇生醫")
    price = c.get("price", "—"); change = c.get("change", "")
    pdate = c.get("priceDate", "")
    wave = (c.get("wave10") or [])[-5:]
    news = (((ns or {}).get("companies") or {}).get(CODE, {}) or {}).get("news", [])[:6]
    score = ((sc or {}).get("companies") or {}).get(CODE, {}) or {}

    try:
        chg_v = float(change)
    except Exception:
        chg_v = 0.0
    chg_col = "#e11d48" if chg_v > 0 else ("#059669" if chg_v < 0 else "#777")

    now = datetime.now(TZ)
    rows = "".join(
        f'<tr><td style="padding:2px 10px">{w.get("date")}</td>'
        f'<td style="padding:2px 10px;text-align:right;font-weight:600">{w.get("close")}</td>'
        f'<td style="padding:2px 10px;text-align:right;color:#999">{w.get("vol")} 張</td></tr>'
        for w in wave)
    news_html = "".join(
        f'<li style="margin:7px 0"><a href="{n.get("link","#")}" '
        f'style="color:#0369a1;text-decoration:none">{n.get("date","")}｜'
        f'{(n.get("title") or "").rsplit(" - ", 1)[0]}</a></li>' for n in news)
    ev_html = "".join(
        f'<li style="margin:5px 0">{q.upper()}｜<b>{ev.get("drug","")}</b> {ev.get("label","")}'
        f'（{ev.get("statusLabel") or ev.get("eventIndication") or "-"}）</li>'
        for q, ev in (c.get("events") or {}).items() if ev)
    total = score.get("total", "—"); band = (score.get("band") or {}).get("label", "")

    html = f"""<div style="font-family:'Helvetica Neue',Arial,sans-serif;max-width:620px;margin:0 auto;color:#1a1a1a">
  <div style="background:#0a0e1a;color:#fff;padding:18px 22px;border-radius:12px 12px 0 0">
    <div style="font-size:12px;color:#00d4ff;letter-spacing:1.5px">📡 台灣生技雷達 · 每日早報</div>
    <div style="font-size:23px;font-weight:700;margin-top:5px">{name} <span style="color:#00d4ff">{CODE}</span></div>
    <div style="font-size:12px;color:#94a3b8;margin-top:3px">{now.strftime('%Y/%m/%d')}（週{'一二三四五六日'[now.weekday()]}）</div>
  </div>
  <div style="border:1px solid #e5e7eb;border-top:none;padding:20px 22px;border-radius:0 0 12px 12px">
    <div style="font-size:16px;margin-bottom:8px">💰 <b>收盤 {price}</b>
      <span style="color:{chg_col};font-weight:700">{change}%</span>
      <span style="color:#aaa;font-size:12px">（資料截至 {pdate}）</span></div>
    <table style="font-size:12px;border-collapse:collapse;margin:4px 0 16px">
      <tr style="color:#999"><td style="padding:2px 10px">日期</td>
      <td style="padding:2px 10px;text-align:right">收盤</td>
      <td style="padding:2px 10px;text-align:right">量</td></tr>{rows}</table>
    <div style="font-size:15px;font-weight:700;margin:16px 0 4px">🎯 AI 評分 {total}
      <span style="font-weight:400;color:#777;font-size:12px">{band}</span></div>
    <div style="font-size:15px;font-weight:700;margin:16px 0 4px">🔬 2026 臨床事件</div>
    <ul style="font-size:13px;padding-left:20px;margin:0">{ev_html or '<li>—</li>'}</ul>
    <div style="font-size:15px;font-weight:700;margin:18px 0 4px">📰 最新消息（{len(news)}）</div>
    <ul style="font-size:13px;padding-left:20px;margin:0">{news_html or '<li>近期無新消息</li>'}</ul>
    <div style="margin-top:20px;text-align:center">
      <a href="{SITE}" style="background:#00d4ff;color:#0a0e1a;padding:10px 22px;border-radius:22px;
      text-decoration:none;font-weight:700;font-size:13px">開啟完整雷達 →</a></div>
    <div style="font-size:11px;color:#b0b0b0;margin-top:18px;border-top:1px solid #eee;padding-top:10px">
      本信由台灣生技雷達自動產生，僅供研究、非投資建議。</div>
  </div>
</div>"""
    subject = f"【藥祇 {CODE} 早報】{now.strftime('%m/%d')} · 收盤 {price} ({change}%)"
    return subject, html


def main():
    subject, html = build()
    if "--dry" in sys.argv:
        with open(os.path.join(BASE, "_email_preview.html"), "w", encoding="utf-8") as f:
            f.write(html)
        print("（乾跑）主旨：", subject)
        print("已輸出預覽 _email_preview.html")
        return
    user = os.environ.get("MAIL_USER"); pw = os.environ.get("MAIL_PASS")
    to = os.environ.get("MAIL_TO") or user
    if not user or not pw:
        print("跳過 email（未設定 MAIL_USER / MAIL_PASS）"); return
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = user
    msg["To"] = to
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(user, pw)
        s.sendmail(user, [to], msg.as_string())
    print(f"✅ 已寄出：{subject} → {to}")


if __name__ == "__main__":
    main()
