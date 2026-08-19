# -*- coding: utf-8 -*-
"""
DHL 對外公告的標準價目表 PDF → 結構化資料

來源(公開,可直接下載):
  https://mydhl.express.dhl/content/dam/downloads/tw/zh/rate-guide/
    service_and_rate_guide_tw_zh_2026.pdf.coredownload.pdf

PDF 結構(2026 年版,29 頁)
  p23–24  國家/區域 → 分區(第 1–8 區)。出口與進口共用同一份分區。
  p25–26  全球國際快遞:出口服務標準價目表
  p27–28  全球通快遞:進口服務標準價目表

每張價目表含:文件表(2.0 公斤以內)、包裹表、每 0.5 公斤加收費用、
每公斤運費(30.1 公斤以上)、Premium 限時服務加價。
價格已含 5% 營業稅,不含燃油與其他附加費。

★ 版面陷阱:同一列的「重量」與「8 個價格」常落在相鄰但不同的 y,
  用單一 y 分組會漏列或錯配。因此一律先鎖定「價格列」,
  再把 y 最接近的重量值配過去(分區表同理)。
"""
from __future__ import annotations

import re
import urllib.request
from pathlib import Path

import fitz

URL = ("https://mydhl.express.dhl/content/dam/downloads/tw/zh/rate-guide/"
       "service_and_rate_guide_tw_zh_2026.pdf.coredownload.pdf")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}

ZONE_PAGES = (23, 24)
EXPORT_PAGES = (25, 26)
IMPORT_PAGES = (27, 28)
N_ZONES = 8
ZONES = [str(i) for i in range(1, N_ZONES + 1)]

PRICE_X_MIN = 100          # 價格欄最左緣(重量欄在 x≈42)
WEIGHT_X_MAX = 100
NUMBER = re.compile(r"^[\d,]+(\.\d+)?\*?$")
ZONE_CELL = re.compile(r"^[1-8](/[1-8])?$")     # 台灣是「-」,中國大陸是「1/2」

# 跨兩區的國家。分界取自 DHL 合約價目表註腳(公開手冊只寫「1/2」未說明)。
SPLIT_ZONES = {
    "中國大陸": [
        ("中國大陸(華南:深圳/廣州/東莞/珠三角)", "1"),
        ("中國大陸(其他地區)", "2"),
    ],
}


def download(dest: Path) -> Path:
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(URL, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    if data[:4] != b"%PDF":
        raise RuntimeError("下載到的不是 PDF")
    dest.write_bytes(data)
    return dest


def num(tok: str) -> float | None:
    t = tok.replace(",", "").rstrip("*")
    try:
        return float(t)
    except ValueError:
        return None


def group_by_y(items, tol: float = 4.0):
    buckets: dict[int, list] = {}
    for w in items:
        buckets.setdefault(round(w[1] / tol), []).append(w)
    return [(k * tol, sorted(v, key=lambda w: w[0])) for k, v in sorted(buckets.items())]


def parse_rate_pages(doc, pages) -> dict:
    out = {
        "zones": ZONES,
        "document": {},           # 2.0 公斤以內之文件
        "parcel": {},             # 包裹
        "extra_per_half_kg": [],  # 每 0.5 公斤加收費用(用來內插未列出的重量)
        "per_kg": [],             # 每公斤運費(30.1 公斤以上,乘以總重)
        "premium": {},            # 限時服務每筆提單加價
    }

    # 每組價目表固定是「第一張文件表、第二張包裹表」,以出現順序判斷段落。
    # 不能靠標題文字:DHL 這份 PDF 的出口頁把第二張表也標成
    # 「2.0公斤以內（含2.0公斤）之文件」(與第一張同字),是官方文件本身的筆誤;
    # 進口頁則正確標為「包裹及2.5公斤以上(含2.5公斤)之文件」。
    table_seq = 0

    for idx, pno in enumerate(pages):
        page = doc[pno - 1]
        words = page.get_text("words")

        labels = []
        for y, ws in group_by_y(words):
            text = "".join(w[4] for w in ws)
            if "重量" in text and "第" in text:
                continue
            if "之文件" in text or "包裹" in text:
                table_seq += 1
                labels.append((y, "document" if table_seq == 1 else "parcel"))
            elif "每0.5公斤加收費用" in text:
                labels.append((y, "extra"))
            elif "每公斤運費" in text:
                labels.append((y, "perkg"))

        # 續頁沒有表格標題,預設延續包裹表
        default_section = None if idx == 0 else "parcel"

        def section_at(y: float, _labels=labels, _default=default_section) -> str | None:
            cur = _default
            for ly, name in _labels:
                if ly <= y:
                    cur = name
            return cur

        # 重量欄的候選值(x < 100)
        weights = [(w[1], num(w[4])) for w in words
                   if w[0] < WEIGHT_X_MAX and NUMBER.match(w[4]) and num(w[4]) is not None]

        # 以「價格列」為主體:同一 y 有 8 個價格欄數字
        for y, ws in group_by_y([w for w in words if w[0] >= PRICE_X_MIN]):
            vals = [num(w[4]) for w in ws if NUMBER.match(w[4])]
            if len(vals) != N_ZONES or any(v is None for v in vals):
                continue
            section = section_at(y)
            if section is None:
                continue
            rate = dict(zip(ZONES, (int(v) for v in vals)))

            if section in ("document", "parcel"):
                near = [(abs(wy - y), wv) for wy, wv in weights if abs(wy - y) <= 8]
                if not near:
                    continue
                weight = min(near)[1]
                out[section][f"{weight:g}"] = rate
                continue

            # 每 0.5 公斤加收 / 每公斤運費:左側是「N 公斤以上」或「A - B」區間
            left = sorted((wy, wv) for wy, wv in weights if abs(wy - y) <= 8)
            nums = [v for _wy, v in left]
            if section == "extra" and nums:
                out["extra_per_half_kg"].append({"from": nums[0], "rate": rate})
            elif section == "perkg" and len(nums) >= 2:
                out["per_kg"].append({"from": nums[0], "to": nums[1], "rate": rate})

    # Premium 加價:整份文字一次比對,比逐列狀態機可靠
    # 例:「DHL 12:00早安件 – …。每筆提單額外加價210 TWD (包含5%營業稅)。」
    joined = " ".join(doc[p - 1].get_text() for p in pages)
    joined = re.sub(r"\s+", " ", joined)
    for m in re.finditer(r"額外加價\s*([\d,]+)\s*TWD", joined):
        before = joined[max(0, m.start() - 160):m.start()]
        tiers = re.findall(r"(12:00|10:30|9:00)", before)
        if tiers:
            out["premium"].setdefault(tiers[-1], float(m.group(1).replace(",", "")))
    return out


def parse_zone_pages(doc) -> dict[str, str]:
    """
    國家/區域 → 分區(出口與進口共用)。
    每列橫排兩組:國家在 x≈42 / 307、分區數字在 x≈141 / 406。
    國名過長會換行、分區數字也常與國名不同 y,故用「就近配對」。
    """
    mapping: dict[str, str] = {}
    for pno in ZONE_PAGES:
        words = doc[pno - 1].get_text("words")
        for name_lo, name_hi, zone_x in ((30, 130, 141), (295, 395, 406)):
            zones = sorted(((w[1], w[4]) for w in words
                            if abs(w[0] - zone_x) < 14 and ZONE_CELL.match(w[4])),
                           key=lambda t: t[0])
            if not zones:
                continue
            parts: dict[int, list[str]] = {}
            for w in words:
                if not (name_lo <= w[0] < name_hi) or w[1] < 195:
                    continue
                if not re.search(r"[一-鿿]", w[4]) or "國家" in w[4]:
                    continue
                i = min(range(len(zones)), key=lambda j: abs(zones[j][0] - w[1]))
                if abs(zones[i][0] - w[1]) <= 9:
                    parts.setdefault(i, []).append(w[4])
            for i, frags in parts.items():
                name, zone = "".join(frags), zones[i][1]
                if "/" in zone:
                    # 目前只有中國大陸是跨兩區(公開手冊寫「1/2」但未說明分界)。
                    # 分界取自 DHL 合約價目表的註腳:
                    #   *1 深圳(SZX)、潮汕惠州(SWA)、珠江三角洲(ZUH)、廣州(CAN)、東莞(DGM) → 第 1 區
                    #   *2 其他地區 → 第 2 區
                    for label, z in SPLIT_ZONES.get(name, []):
                        mapping[label] = z
                    continue
                mapping[name] = zone
    return mapping


def parse(pdf: Path) -> dict:
    doc = fitz.open(pdf)
    return {
        "carrier": "DHL",
        "kind": "public",
        "effective": "2026-01-01",
        "currency": "TWD",
        "tax_included": True,
        "fuel_included": False,
        "source": URL,
        "rounding": {"under_30": 0.5, "over_30": 1.0,
                     "note": "每箱進位 0.5kg;總重 30kg 以內進位 0.5kg,30kg 以上進位 1kg"},
        "zone_map": parse_zone_pages(doc),
        "services": {
            "export": parse_rate_pages(doc, EXPORT_PAGES),
            "import": parse_rate_pages(doc, IMPORT_PAGES),
        },
    }


if __name__ == "__main__":
    import json
    root = Path(__file__).resolve().parents[1]
    data = parse(download(root / "_source" / "dhl_rate_guide_2026.pdf"))
    for name, svc in data["services"].items():
        ws = sorted(float(k) for k in svc["parcel"])
        print(f"  {name:7s} 文件 {len(svc['document'])} 檔 · 包裹 {len(svc['parcel'])} 檔"
              f"({ws[0]}~{ws[-1]}) · 加收 {len(svc['extra_per_half_kg'])} 段 · "
              f"每公斤 {len(svc['per_kg'])} 段 · Premium {svc['premium']}")
    print(f"  分區對照 {len(data['zone_map'])} 個國家/區域")
    print("  抽查:", json.dumps({k: data["zone_map"].get(k) for k in
          ("美國", "中國大陸", "日本", "越南", "德國", "南非", "香港特別行政區")}, ensure_ascii=False))
