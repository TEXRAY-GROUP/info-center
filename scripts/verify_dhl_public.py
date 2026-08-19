# -*- coding: utf-8 -*-
"""DHL 公告價解析對帳:逐格比對 PDF 原文"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_dhl_public import parse, download          # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PDF = download(ROOT / "_source" / "dhl_rate_guide_2026.pdf")
D = parse(PDF)
doc = fitz.open(PDF)
fails = 0


def check(label, got, want):
    global fails
    ok = str(got) == str(want)
    fails += 0 if ok else 1
    print(f"  {'✅' if ok else '❌'} {label}: 解析={got} 原文={want}")


def pdf_row(pno: int, y: float) -> list[str]:
    """取 PDF 指定頁、指定 y 附近的 8 個價格"""
    ws = [w for w in doc[pno - 1].get_text("words")
          if abs(w[1] - y) < 4 and w[0] >= 100]
    ws.sort(key=lambda w: w[0])
    return [w[4].replace(",", "") for w in ws]


Z = [str(i) for i in range(1, 9)]
print(f"版本 {D['effective']} · 含稅 {D['tax_included']}")

print("\n[1] 費率抽驗(對 PDF 原文逐格)")
check("出口 文件 0.5kg",
      ",".join(str(D["services"]["export"]["document"]["0.5"][z]) for z in Z),
      ",".join(pdf_row(25, 230.8)))
check("出口 包裹 1.5kg",
      ",".join(str(D["services"]["export"]["parcel"]["1.5"][z]) for z in Z),
      ",".join(pdf_row(25, 333)))
check("出口 包裹 30kg",
      ",".join(str(D["services"]["export"]["parcel"]["30"][z]) for z in Z),
      ",".join(pdf_row(26, 378)))
check("出口 包裹 70kg",
      ",".join(str(D["services"]["export"]["parcel"]["70"][z]) for z in Z),
      ",".join(pdf_row(26, 438)))

print("\n[2] 每公斤 / 每 0.5 公斤加收")
ex = D["services"]["export"]
check("每公斤段數", len(ex["per_kg"]), 3)
check("每公斤 30.1–70 第1區", ex["per_kg"][0]["rate"]["1"], 421)
check("每公斤 300.1–3000 第1區", ex["per_kg"][-1]["rate"]["1"], 470)
check("加收段數", len(ex["extra_per_half_kg"]), 2)
check("加收 10kg 以上 第1區", ex["extra_per_half_kg"][0]["rate"]["1"], 43)

print("\n[3] Premium 加價(含稅)")
check("出口 12:00", ex["premium"].get("12:00"), 210.0)
check("出口 10:30", ex["premium"].get("10:30"), 420.0)
check("出口 9:00", ex["premium"].get("9:00"), 1260.0)
imp = D["services"]["import"]["premium"]
print(f"  ℹ 進口只有 {sorted(imp)} —— PDF 進口頁確實未提供 10:30 快件,非解析遺漏")

print("\n[4] 重量級距完整性")
for name in ("export", "import"):
    ws = sorted(float(k) for k in D["services"][name]["parcel"])
    dup = len(ws) != len(set(ws))
    print(f"  {name}: {len(ws)} 檔 {ws[0]}~{ws[-1]}{'  ❌ 有重複' if dup else '  ✅'}")
    fails += 1 if dup else 0

print("\n[5] 分區對照")
zm = D["zone_map"]
print(f"  共 {len(zm)} 個國家/區域")
for k in ("美國", "日本", "越南", "德國", "南非", "香港特別行政區",
          "中國大陸(華南:深圳/廣州/東莞/珠三角)", "中國大陸(其他地區)"):
    v = zm.get(k)
    ok = v is not None
    fails += 0 if ok else 1
    print(f"  {'✅' if ok else '❌'} {k}: 第 {v} 區")
check("台灣不應出現(無分區)", "台灣" in zm, False)

print(f"\n{'='*52}\n{'✅ 全部通過' if fails == 0 else f'❌ 有 {fails} 項不符'}")
sys.exit(1 if fails else 0)
