# -*- coding: utf-8 -*-
"""
原物料價格積木 — 抓取器

輸出:data/materials.json

資料來源(皆為公開、免金鑰)
  新浪財經 期貨日K線   PTA、滌綸短纖、乙二醇、鄭商所棉花(人民幣/噸)
  Yahoo Finance 期貨   美棉(美分/磅)、布蘭特/WTI 原油(美元/桶)、天然氣(美元/MMBtu)

★ 一律只取「日K線」,不用即時報價。
  新浪的即時報價與日K線在主力合約換月時定義不同、數字對不上
  (實測 PTA 即時 5,762 vs 日K線 8/18 收 5,958),混用會讓漲跌算錯。
  代價是顯示收盤價而非盤中價,對趨勢判斷沒有影響,但日期一定要標清楚。

單位換算在前端做(需要匯率,由 data/rates.json 提供):
  cny_per_ton  人民幣/噸  → 台幣/公斤:price / 1000 * CNY匯率
  usc_per_lb   美分/磅    → 台幣/公斤:price / 100 / 0.45359237 * USD匯率
  none         原油與天然氣不換算(美元/桶換成台幣/公斤沒有意義)
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
SINA_REFERER = {"Referer": "https://finance.sina.com.cn"}
SINA_KLINE = ("https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_x=/"
              "InnerFuturesNewService.getDailyKLine?symbol={}")
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{}?range=2y&interval=1d"

GROUPS = [
    ("polyester", "聚酯鏈"),
    ("cotton", "棉花"),
    ("energy", "能源"),
]

# id, 顯示名, 群組, 來源, 代號, 單位標示, 換算方式, 說明
ITEMS = [
    ("pta", "PTA", "polyester", "sina", "TA0", "人民幣/噸", "cny_per_ton",
     "聚酯的主要原料,聚酯鏈價格的領先指標"),
    ("pf", "滌綸短纖", "polyester", "sina", "PF0", "人民幣/噸", "cny_per_ton",
     "最接近成品的聚酯原料"),
    ("meg", "乙二醇 MEG", "polyester", "sina", "EG0", "人民幣/噸", "cny_per_ton",
     "聚酯的另一原料,與 PTA 並列上游"),
    ("cotton_cn", "中國棉花", "cotton", "sina", "CF0", "人民幣/噸", "cny_per_ton",
     "鄭商所棉花期貨,反映中國內盤"),
    ("cotton_us", "美棉", "cotton", "yahoo", "CT=F", "美分/磅", "usc_per_lb",
     "ICE 2 號棉花期貨,國際基準"),
    ("brent", "布蘭特原油", "energy", "yahoo", "BZ=F", "美元/桶", "none",
     "聚酯鏈的最上游成本"),
    ("wti", "WTI 原油", "energy", "yahoo", "CL=F", "美元/桶", "none",
     "美國原油基準,與布蘭特高度連動"),
    ("gas", "天然氣", "energy", "yahoo", "NG=F", "美元/MMBtu", "none",
     "染整燃料成本相關"),
]

HISTORY = 400          # 保留約 1.5 年日線,足夠畫 365 天走勢
TPE = timezone(timedelta(hours=8))
OUT = Path(__file__).resolve().parents[1] / "data" / "materials.json"


def get(url: str, headers: dict | None = None) -> str:
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def fetch_sina(symbol: str) -> list[tuple[str, float]]:
    """新浪期貨日K線,回傳 [(日期, 收盤價), ...]"""
    body = get(SINA_KLINE.format(symbol), SINA_REFERER)
    m = re.search(r"\((\[.*\])\)", body, re.S)
    if not m:
        raise RuntimeError("回傳格式非預期(可能改版)")
    rows = json.loads(m.group(1))
    return [(r["d"], float(r["c"])) for r in rows if r.get("c")]


def fetch_yahoo(symbol: str) -> list[tuple[str, float]]:
    d = json.loads(get(YAHOO.format(symbol)))["chart"]["result"][0]
    stamps = d["timestamp"]
    closes = d["indicators"]["quote"][0]["close"]
    out = []
    for ts, c in zip(stamps, closes):
        if c is None:
            continue
        day = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        out.append((day, float(c)))
    return out


def main() -> int:
    now = datetime.now(TPE)
    items, failed = [], []

    for iid, name, group, src, symbol, unit, convert, note in ITEMS:
        try:
            series = fetch_sina(symbol) if src == "sina" else fetch_yahoo(symbol)
        except Exception as err:                  # noqa: BLE001 — 單項失敗不該中斷整批
            print(f"  ❌ {name}({symbol}):{type(err).__name__}: {err}", file=sys.stderr)
            failed.append(name)
            continue
        if len(series) < 2:
            print(f"  ❌ {name}({symbol}):資料點不足", file=sys.stderr)
            failed.append(name)
            continue

        series = series[-HISTORY:]
        (last_day, last), (prev_day, prev) = series[-1], series[-2]
        change = round(last - prev, 4)
        pct = round((last - prev) / prev * 100, 3) if prev else None

        items.append({
            "id": iid, "name": name, "group": group, "note": note,
            "source": "新浪財經 期貨日K線" if src == "sina" else "Yahoo Finance",
            "symbol": symbol, "unit": unit, "convert": convert,
            "date": last_day, "price": last, "prev": prev,
            "change": change, "change_pct": pct,
            "history": [[d, p] for d, p in series],
        })
        arrow = "▲" if change > 0 else "▼" if change < 0 else "－"
        print(f"  {name:10s} {last:>12,.2f} {unit:10s} {arrow} {abs(change):>8,.2f} "
              f"({pct:+.2f}%)  {last_day}  {len(series)} 筆")

    if not items:
        print("全部來源都失敗,不覆蓋既有資料", file=sys.stderr)
        return 1

    out = {
        "block": "materials",
        "title": "原物料價格",
        "fetched_at": now.isoformat(timespec="seconds"),
        "note": "期貨收盤價,非實際採購報價。聚酯鏈與棉花可換算台幣/公斤參考;"
                "原油與天然氣不換算(單位性質不同,換算沒有意義)。",
        "groups": [{"id": g, "label": lab} for g, lab in GROUPS],
        "items": items,
        "failed": failed,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"\n已寫入 {OUT}({OUT.stat().st_size/1024:.0f} KB)"
          + (f",{len(failed)} 項失敗:{failed}" if failed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
