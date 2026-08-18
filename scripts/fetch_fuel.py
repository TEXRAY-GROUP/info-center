# -*- coding: utf-8 -*-
"""
燃油附加費抓取

DHL:官網燃油費率表是伺服器端渲染在 HTML 裡(非 JS 載入),可直接解析。
     https://mydhl.express.dhl/tw/zh/ship/surcharges.html
     取表頭為「生效日 / 附加費用」的表格,列如 ['8月 17-23, 2026', '42.00%']。
FedEx:官網全站對程式抓取回傳 Akamai 阻擋頁,**無法自動抓**,採人工維護
     (數值寫在 data/fuel_manual.json,由專人每週更新)。

輸出:data/fuel.json —— 這份只有兩個百分比,不含任何機密資料,
      可以放到公開的 GitHub Pages 供內部版工具跨域取用。
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

URL = "https://mydhl.express.dhl/tw/zh/ship/surcharges.html"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9",
}
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "fuel.json"
MANUAL = ROOT / "data" / "fuel_manual.json"
TPE = timezone(timedelta(hours=8))

MONTH_RANGE = re.compile(r"(\d{1,2})月\s*(\d{1,2})-(?:(\d{1,2})月\s*)?(\d{1,2}),\s*(\d{4})")


def strip_tags(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def fetch_dhl() -> list[dict]:
    req = urllib.request.Request(URL, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        html = r.read().decode("utf-8", "replace")

    for table in re.findall(r"<table.*?</table>", html, re.S):
        rows = re.findall(r"<tr.*?</tr>", table, re.S)
        parsed = []
        for row in rows:
            cells = [strip_tags(c) for c in re.findall(r"<t[dh].*?</t[dh]>", row, re.S)]
            if len(cells) == 2:
                parsed.append(cells)
        if not parsed or parsed[0] != ["生效日", "附加費用"]:
            continue
        weeks = []
        for date_txt, pct_txt in parsed[1:]:
            m = MONTH_RANGE.search(date_txt)
            pm = re.search(r"([\d.]+)\s*%", pct_txt)
            if not (m and pm):
                continue
            m1, d1, m2, d2, year = m.groups()
            m2 = m2 or m1
            weeks.append({
                "label": date_txt,
                "start": f"{year}-{int(m1):02d}-{int(d1):02d}",
                "end": f"{year}-{int(m2):02d}-{int(d2):02d}",
                "percent": float(pm.group(1)),
            })
        if weeks:
            return weeks
    raise RuntimeError("找不到 DHL 燃油費率表(頁面結構可能已改版)")


def current_week(weeks: list[dict], today: str) -> dict:
    for w in weeks:
        if w["start"] <= today <= w["end"]:
            return w
    return weeks[0]                                   # 表格第一列即最新一週


def main() -> int:
    today = datetime.now(TPE).strftime("%Y-%m-%d")
    weeks = fetch_dhl()
    cur = current_week(weeks, today)
    print(f"DHL 燃油:{cur['label']} = {cur['percent']}%(共取得 {len(weeks)} 週)")

    manual = {}
    if MANUAL.exists():
        manual = json.loads(MANUAL.read_text(encoding="utf-8"))
    fedex = manual.get("fedex", {})
    if fedex:
        print(f"FedEx 燃油(人工):{fedex.get('percent')}% "
              f"(資料日 {fedex.get('as_of')},{fedex.get('label', '')})")
    else:
        print("FedEx 燃油:尚未提供人工數值")

    out = {
        "updated_at": datetime.now(TPE).isoformat(timespec="seconds"),
        "dhl": {
            "percent": cur["percent"],
            "label": cur["label"],
            "start": cur["start"],
            "end": cur["end"],
            "source": URL,
            "auto": True,
            "history": weeks,
        },
        "fedex": {
            "percent": fedex.get("percent"),
            "label": fedex.get("label", ""),
            "as_of": fedex.get("as_of"),
            "source": "https://www.fedex.com/zh-tw/shipping/surcharges.html",
            "auto": False,
            "note": "FedEx 官網封鎖程式抓取,此數值由人工維護。",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已寫入 {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
