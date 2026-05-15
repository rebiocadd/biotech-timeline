#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""共用模組：更新 status.json 中各任務的最後執行時間"""
import json, os
from datetime import datetime

STATUS_PATH = os.path.join(os.path.dirname(__file__), "status.json")

def update_status(task, extra=None):
    """
    task: 'prices' | 'holders' | 'news'
    extra: 額外要記錄的欄位 dict（例如 holders 的 dataDate）
    """
    now = datetime.now()
    data = {}
    if os.path.exists(STATUS_PATH):
        try:
            with open(STATUS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    entry = {
        "lastRun": now.strftime("%Y/%m/%d %H:%M"),
        "lastRunDate": now.strftime("%m/%d"),
    }
    if extra:
        entry.update(extra)
    data[task] = entry
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
