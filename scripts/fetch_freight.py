# -*- coding: utf-8 -*-
"""
運費試算積木 — 抓取器

把 DHL 與 FedEx **對外公告的標準價目表**整理成一份 data/freight.json,
供網頁試算台灣出口 / 進口的快遞運費。

⚠ 只用公告價。本站為公開 repo,不得放入公司議定的合約價。
⚠ 第三地(起訖點皆非台灣)不做:DHL 未公開第三地價目表,做出來只有單邊報價沒有比較意義。

資料來源(皆為兩家官網公開的 PDF,可程式直接下載)
  DHL   國際快遞服務手冊(出口/進口標準價目表 + 國家分區)
  FedEx 台灣出口價目表、ImportOne 進口價目表、服務地區一覽表
兩家價格皆已含 5% 營業稅,皆不含燃油附加費(燃油另由 data/fuel.json 提供)。
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parse_dhl_public as dhlmod                      # noqa: E402
import parse_fedex_public as fxmod                     # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "freight.json"
TPE = timezone(timedelta(hours=8))

CJK = re.compile(r"[一-鿿·]+")
POSTAL = re.compile(r"\d{4,}[-–]\d{4,}")
SUBREGION = re.compile(r"^[A-Za-z][A-Za-z .()'’\-]*\d{4,}\s*[-–]\s*\d{4,}")

# 兩家譯名不同者。左為 FedEx 用字,右為 DHL 用字。
ALIAS_DHL = {
    "中國華南地區": "中國大陸(華南:深圳/廣州/東莞/珠三角)",
    "中國": "中國大陸(其他地區)",
    "印尼": "印度尼西亞",
    "史瓦濟南": "史瓦帝尼",
    "香港": "香港特別行政區",
    "澳門": "澳門特別行政區",
    "南韓": "南韓",
}
# DHL 把美國視為單一分區,FedEx 分美西/美東,兩邊都保留
ALIAS_DHL_US = "美國"

SUFFIX = ("群島", "共和國", "特別行政區", "島", "地區")


def chinese_of(name: str) -> str:
    """中英混排字串取中文主名。取第一段——最長的那段可能是省州名。"""
    parts = CJK.findall(POSTAL.sub("", name))
    return parts[0] if parts else ""


def loose(name: str) -> str:
    for s in SUFFIX:
        if name.endswith(s) and len(name) > len(s) + 1:
            return name[: -len(s)]
    return name


def match_name(zh: str, pool) -> str | None:
    """精確 → 剝字尾 → 互為子字串(取最短,避免誤配長名)"""
    keys = list(pool)
    if zh in pool:
        return zh
    lz = loose(zh)
    for k in keys:
        if loose(k) == lz:
            return k
    cands = [k for k in keys if lz and (lz in k or loose(k) in zh)]
    return min(cands, key=len) if cands else None


def build_countries(dhl_zones: dict, fx_zones: dict) -> tuple[list[dict], list[str]]:
    """以 FedEx 清單為基準(顆粒度較細),往 DHL 配對"""
    countries, unmatched, seen = [], [], set()
    for raw, zones in fx_zones.items():
        if SUBREGION.match(raw):        # 州/省的郵遞區號明細列,不是可寄送的國家
            continue
        zh = chinese_of(raw)
        if not zh or zh in seen:
            continue
        seen.add(zh)

        key = ALIAS_DHL.get(zh)
        if key is None:
            key = ALIAS_DHL_US if zh.startswith("美國") else match_name(zh, dhl_zones)
        dhl_zone = dhl_zones.get(key) if key else None
        if not dhl_zone:
            unmatched.append(zh)

        countries.append({
            "name": zh,
            "aliases": [key] if key and key != zh else [],
            "dhl_zone": dhl_zone,
            "fedex_zones": zones,
        })
    countries.sort(key=lambda c: c["name"])
    return countries, unmatched


def main() -> int:
    dhl_pdf = dhlmod.download(ROOT / "_source" / "dhl_rate_guide_2026.pdf")
    dhl = dhlmod.parse(dhl_pdf)
    print(f"  DHL   分區 {len(dhl['zone_map'])} 國 · "
          f"出口包裹 {len(dhl['services']['export']['parcel'])} 檔")

    fx = json.loads((ROOT / "data" / "fedex_public.json").read_text(encoding="utf-8"))
    print(f"  FedEx 分區 {len(fx['zone_table'])} 國 · "
          f"出口服務 {sorted(fx['services']['export'])}")

    countries, unmatched = build_countries(dhl["zone_map"], fx["zone_table"])
    both = sum(1 for c in countries if c["dhl_zone"] and c["fedex_zones"])
    print(f"  合併後 {len(countries)} 國,其中 {both} 國兩家皆可試算")
    if unmatched:
        print(f"  ⚠ DHL 對不到 {len(unmatched)} 國(將只顯示 FedEx):{unmatched[:8]}")

    out = {
        "block": "freight",
        "title": "運費試算(公告價)",
        "kind": "public",
        "fetched_at": datetime.now(TPE).isoformat(timespec="seconds"),
        "note": "兩家皆為對外公告標準價,已含 5% 營業稅,不含燃油附加費、關稅、"
                "偏遠地區與旺季附加費。實際運費以承攬商報價為準。",
        "scope": "台灣出口 / 進口。第三地(起訖點皆非台灣)無公開價目表,不提供試算。",
        "dhl": {
            "effective": dhl["effective"],
            "source": dhl["source"],
            "rounding": dhl["rounding"],
            "services": dhl["services"],
        },
        "fedex": {
            "effective": fx["effective"],
            "source": fx["source"],
            "services": fx["services"],
        },
        "countries": countries,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"\n已寫入 {OUT}({OUT.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
