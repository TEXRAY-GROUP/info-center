# -*- coding: utf-8 -*-
"""
FedEx 公告價(標準價目表)PDF → JSON

用途:FedEx 合約價只涵蓋第三方(3P),台灣出口/進口改用對外公告的標準價。
來源(公開,可自動下載;**直接抓會被 Akamai 擋,必須帶 Referer**):
  https://www.fedex.com/content/dam/fedex/international/rates/
    fedex-rates-exp-zh-tw-2026.pdf  台灣出口推廣價目表(IPE/IP/IPF/IE/IEF)
    fedex-rates-imp-zh-tw-2026.pdf  台灣 ImportOne 進口價目表(IP/IPF/IE/IEF)
    fedex-rates-zi-zh-tw-2026.pdf   服務地區一覽表(國家→分區,分出口/進口)
公告價**已含台灣營業稅**,不含燃油與其他特別費。

版面重點
  一般費率頁:表頭「新台幣 A B … I」定義分區欄的 x 座標;
              依序為 快遞封(定額)、快遞袋(0.50–2.50)、包裹(0.50 起)。
              「快遞封 ³ 公斤」的 3 是上標註腳,不是重量。
  大貨頁:同一頁有多個交付方式區段(府對府 DTD / 府到機場 DTA / …),
          列為重量區間(68-99、100-299…1000+)的每公斤費率。
  地區表:每列橫向排 3 組國家,每組 6 個分區欄(出口 3 + 進口 3),
          分區字母後面可能跟著上標 ¹。
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

import fitz

BASE = "https://www.fedex.com/content/dam/fedex/international/rates/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Referer": "https://www.fedex.com/zh-tw/shipping/rates.html",   # 少了這行會被擋
}
# 年度價目表:FedEx 每年初換版,檔名與生效日都帶年份。
# 明年更新時只改這一個常數即可(生效日若非 1/5 要一併確認)。
# 提醒機制見 .github/workflows/freight-annual-check.yml
RATE_YEAR = 2026

FILES = {
    "export": f"fedex-rates-exp-zh-tw-{RATE_YEAR}.pdf",
    "import": f"fedex-rates-imp-zh-tw-{RATE_YEAR}.pdf",
    "zones": f"fedex-rates-zi-zh-tw-{RATE_YEAR}.pdf",
}
SRC_DIR = Path(__file__).resolve().parents[1] / "_source"
OUT = Path(__file__).resolve().parents[1] / "data" / "fedex_public.json"

NUM = re.compile(r"^[\d,]+(\.\d+)?$")
RANGE = re.compile(r"^(\d+)-(\d+)$|^(\d+)\+$")
ZONE_LETTER = re.compile(r"^([A-Z])[¹²³⁴]?$")

SERVICE_KEYS = [
    ("國際優先快遞特快服務", "IPE"),
    ("國際優先快遞大貨服務", "IPF"),
    ("國際經濟快遞大貨服務", "IEF"),
    ("國際優先快遞服務", "IP"),
    ("國際經濟快遞服務", "IE"),
]
DELIVERY_MODES = [("府對府", "DTD"), ("府到機場", "DTA"),
                  ("機場到府", "ATD"), ("機場到機場", "ATA")]


def download(name: str) -> Path:
    dest = SRC_DIR / name
    if dest.exists():
        return dest
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(BASE + name, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    if data[:4] != b"%PDF":
        raise RuntimeError(f"{name} 下載到的不是 PDF(可能被 Akamai 擋)")
    dest.write_bytes(data)
    print(f"  下載 {name} ({len(data)/1024:.0f} KB)")
    return dest


def rows_of(page, tol: float = 3.0):
    buckets: dict[int, list] = {}
    for w in page.get_text("words"):
        buckets.setdefault(round(w[1] / tol), []).append(w)
    return [(k * tol, sorted(v, key=lambda w: w[0])) for k, v in sorted(buckets.items())]


def zone_columns(page) -> list[tuple[str, float]]:
    """由「新台幣 A B … I」表頭取得各分區欄的中心 x"""
    for _y, ws in rows_of(page):
        letters = [(w[4], (w[0] + w[2]) / 2) for w in ws if re.fullmatch(r"[A-Z]", w[4])]
        if len(letters) >= 8:
            return letters
    return []


def row_prices(ws, cols) -> dict[str, int] | None:
    """把一列裡落在分區欄位置的數字對齊到分區"""
    left_edge = min(x for _z, x in cols) - 14
    hits = [w for w in ws if NUM.match(w[4]) and (w[0] + w[2]) / 2 > left_edge]
    if len(hits) != len(cols):
        return None
    row = {}
    for w in hits:
        cx = (w[0] + w[2]) / 2
        row[min(cols, key=lambda t: abs(t[1] - cx))[0]] = int(w[4].replace(",", ""))
    return row if len(row) == len(cols) else None


def parse_normal_page(page, code: str, cols) -> dict:
    """一般費率頁:快遞封 / 快遞袋 / 包裹"""
    out = {"code": code, "zones": [z for z, _x in cols],
           "envelope": {}, "pak": {}, "parcel": {}, "per_kg": []}
    section = None
    last_w = None
    for _y, ws in rows_of(page):
        text = "".join(w[4] for w in ws)
        prices = row_prices(ws, cols)

        if "快遞封" in text:
            # 「快遞封 ³ 公斤」的 3 是上標註腳。價格可能與標題同列,也可能在下一列
            if prices:
                out["envelope"] = prices
                section = None
            else:
                section = "envelope"
            continue
        if section == "envelope" and prices:
            out["envelope"] = prices
            section = None
            continue
        if "快遞袋" in text:
            # 快遞袋第一列(0.50)的價格與標題同一列,重量寫在下一列
            if prices:
                out["pak"]["0.5"] = prices
                last_w = 0.5
            section = "pak"
            continue
        if not prices:
            continue

        # 20.5 公斤之後接「每公斤運費」區段:重量區間 21-44、45-70、…、1000+
        rng = next((t for t in (w[4] for w in ws) if RANGE.match(t)), None)
        if rng:
            m = RANGE.match(rng)
            lo, hi = (int(m.group(1)), int(m.group(2))) if m.group(1) else (int(m.group(3)), 99999)
            out["per_kg"].append({"from": lo, "to": hi, "rate": prices})
            continue

        left = [w[4] for w in ws
                if (w[0] + w[2]) / 2 < min(x for _z, x in cols) - 14 and NUM.match(w[4])]
        if not left:
            continue
        weight = float(left[-1].replace(",", ""))
        # 重量回頭變小 → 快遞袋結束,進入包裹段
        if last_w is not None and weight <= last_w:
            section = "parcel"
        last_w = weight
        (out["pak"] if section == "pak" else out["parcel"])[f"{weight:g}"] = prices
    return out


def parse_bulk_page(page, code: str) -> dict:
    """大貨頁:一頁含多個交付方式區段,每段為重量區間的每公斤費率"""
    out = {"code": code, "zones": [], "per_kg": {}}
    cols: list[tuple[str, float]] = []
    mode = None
    for _y, ws in rows_of(page):
        text = "".join(w[4] for w in ws)
        letters = [(w[4], (w[0] + w[2]) / 2) for w in ws if re.fullmatch(r"[A-Z]", w[4])]
        if len(letters) >= 8:
            cols = letters
            out["zones"] = [z for z, _x in cols]
            continue
        for label, key in DELIVERY_MODES:
            if label in text:
                mode = key
                out["per_kg"].setdefault(mode, [])
                break
        if not cols or not mode:
            continue
        rng = next((t for t in (w[4] for w in ws) if RANGE.match(t)), None)
        if not rng:
            continue
        prices = row_prices(ws, cols)
        if not prices:
            continue
        m = RANGE.match(rng)
        lo, hi = (int(m.group(1)), int(m.group(2))) if m.group(1) else (int(m.group(3)), 99999)
        out["per_kg"][mode].append({"from": lo, "to": hi, "rate": prices})
    return out


def parse_zone_table(doc) -> dict[str, dict[str, str]]:
    """
    服務地區一覽表 → { 國家名: {出口/進口 各服務的分區} }
    每列橫排 3 組;每組 6 個分區欄:
      出口 IPE/BOX(IPE)、IP/BOX(IP)、IPF/IE/IEF;進口同樣三欄。
    """
    fields = ["exp_IPE", "exp_IP", "exp_IPF_IE_IEF", "imp_IPE", "imp_IP", "imp_IPF_IE_IEF"]
    result: dict[str, dict[str, str]] = {}

    for page in doc:
        # 表頭:找出三組「國家或地區」的 x,以及每組 6 個分區欄的 x
        head = None
        for _y, ws in rows_of(page):
            # 每頁的組數不一定(第 1 頁 3 組、第 2 頁 2 組)
            if sum(1 for w in ws if w[4] == "國家或地區") >= 2:
                head = ws
                break
        if not head:
            continue
        name_x = [w[0] for w in head if w[4] == "國家或地區"]

        # 表頭欄名會換行(IPF/ 與 IE/IEF 分兩行),x 座標擠在一起不可用,
        # 改由資料列的分區字母自行分群求出 6 個欄位中心。
        words = page.get_text("words")
        groups = []
        for gi, nx in enumerate(name_x):
            nx_end = name_x[gi + 1] if gi + 1 < len(name_x) else 10_000
            xs = sorted((w[0] + w[2]) / 2 for w in words
                        if nx <= w[0] < nx_end and w[1] > 125 and ZONE_LETTER.match(w[4]))
            cols: list[float] = []
            cluster = [xs[0]] if xs else []
            for x in xs[1:]:
                if x - cluster[-1] > 8:
                    cols.append(sum(cluster) / len(cluster))
                    cluster = []
                cluster.append(x)
            if cluster:
                cols.append(sum(cluster) / len(cluster))
            groups.append((nx, nx_end, cols[:6]))
        for nx, nx_end, cols in groups:
            if len(cols) < 6:
                continue
            # 每個國家有 6 個分區字母,但可能跨兩行排版。
            # 依 (y, x) 讀序掃描,欄位索引「回頭」就代表換一個國家。
            letters = sorted(
                [w for w in words
                 if nx <= w[0] < nx_end and w[1] > 125 and ZONE_LETTER.match(w[4])],
                key=lambda w: (round(w[1] / 3), w[0]))
            letter_rows: list[tuple[float, list]] = []
            cur: list = []
            last_ci = -1
            for w in letters:
                cx = (w[0] + w[2]) / 2
                ci = min(range(len(cols)), key=lambda i: abs(cols[i] - cx))
                if ci <= last_ci and cur:
                    letter_rows.append((cur[0][1], cur))
                    cur = []
                cur.append(w)
                last_ci = ci
            if cur:
                letter_rows.append((cur[0][1], cur))
            letter_rows = [(y, ws) for y, ws in letter_rows if len(ws) == 6]
            if not letter_rows:
                continue
            name_words = sorted(
                [w for w in words
                 if nx <= w[0] < cols[0] - 6 and w[1] > 125 and not ZONE_LETTER.match(w[4])],
                key=lambda w: w[1])

            # 國名可能佔 1~2 行,且一律在自己那列分區字母的同一行或上方。
            # 因此把每個國名字串歸給「第一個 y 不小於它的字母列」。
            row_y = [y for y, _ in letter_rows]
            buckets: dict[int, list[str]] = {}
            for w in name_words:
                idx = next((i for i, y in enumerate(row_y) if y >= w[1] - 3), None)
                if idx is not None:
                    buckets.setdefault(idx, []).append(w[4])

            for i, (_y, ws) in enumerate(letter_rows):
                name = "".join(buckets.get(i, [])).strip()
                if not name:
                    continue
                zs = [ZONE_LETTER.match(w[4]).group(1) for w in ws][:6]
                result[name] = dict(zip(fields, zs))
    return result


def main() -> int:
    print("FedEx 公告價")
    out = {
        "carrier": "FedEx", "kind": "public", "confidential": False,
        "currency": "TWD", "tax_included": True, "fuel_included": False,
        "effective": f"{RATE_YEAR}-01-05", "source": BASE,
        "note": "公告推廣價,已含台灣營業稅,不含燃油附加費與其他特別費。",
        "services": {"export": {}, "import": {}},
    }

    for direction in ("export", "import"):
        doc = fitz.open(download(FILES[direction]))
        for page in doc:
            head = page.get_text()[:300]
            code = next((c for kw, c in SERVICE_KEYS if kw in head), None)
            if not code:
                continue
            if code in ("IPF", "IEF"):
                parsed = parse_bulk_page(page, code)
                out["services"][direction][code] = parsed
                seg = {k: len(v) for k, v in parsed["per_kg"].items()}
                print(f"  {direction:6s} {code:4s} 大貨 分區 {len(parsed['zones'])} · 交付方式 {seg}")
            else:
                cols = zone_columns(page)
                if not cols:
                    continue
                parsed = parse_normal_page(page, code, cols)
                out["services"][direction][code] = parsed
                ws = sorted(float(k) for k in parsed["parcel"]) or [0]
                print(f"  {direction:6s} {code:4s} 分區 {len(parsed['zones'])} · "
                      f"包裹 {len(parsed['parcel'])} 檔({ws[0]}~{ws[-1]}) · "
                      f"快遞袋 {len(parsed['pak'])} 檔 · 快遞封 {'有' if parsed['envelope'] else '無'} · "
                      f"每公斤段 {len(parsed['per_kg'])}")

    out["zone_table"] = parse_zone_table(fitz.open(download(FILES["zones"])))
    print(f"  服務地區一覽表 {len(out['zone_table'])} 個國家/地區")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已寫入 {OUT}({OUT.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
