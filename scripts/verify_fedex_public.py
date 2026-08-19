# -*- coding: utf-8 -*-
"""FedEx 公告價 JSON 對帳"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
D = json.loads((ROOT / "data" / "fedex_public.json").read_text(encoding="utf-8"))
EXP = ROOT / "_source" / "fedex-rates-exp-zh-tw-2026.pdf"

fails = 0


def check(label, got, want):
    global fails
    ok = str(got) == str(want)
    fails += 0 if ok else 1
    print(f"  {'✅' if ok else '❌'} {label}: 解析={got} 期望={want}")


print(f"生效日:{D['effective']} | 含稅:{D['tax_included']}")

# ---------- 1. 費率抽驗 ----------
print("\n[1] 費率抽驗(對 PDF 原文)")
doc = fitz.open(EXP)


def pdf_rows(page_no, first):
    buckets = {}
    for w in doc[page_no - 1].get_text("words"):
        buckets.setdefault(round(w[1] / 3), []).append(w)
    hits = []
    for _k, ws in sorted(buckets.items()):
        toks = [x[4] for x in sorted(ws, key=lambda x: x[0])]
        if first in toks:
            nums = [t.replace(",", "") for t in toks if t.replace(",", "").isdigit()]
            if len(nums) >= 9:
                hits.append(nums[-9:])
    return hits


Z = list("ABCDEFGHI")
ipe = D["services"]["export"]["IPE"]

check("IPE 快遞封(定額)", ",".join(str(ipe["envelope"][z]) for z in Z),
      "1315,1427,1688,1747,2060,2223,2646,3341,1429")
check("IPE 快遞袋 0.5", ",".join(str(ipe["pak"]["0.5"][z]) for z in Z),
      "1559,1646,1973,2027,2429,2613,3052,3656,1634")
check("IPE 快遞袋 2.5", ",".join(str(ipe["pak"]["2.5"][z]) for z in Z),
      "4883,5010,5305,5332,5405,5845,6789,8165,4968")
check("IPE 包裹 0.5", ",".join(str(ipe["parcel"]["0.5"][z]) for z in Z),
      "2937,3074,3696,3755,3645,4101,4937,6258,3082")
check("IPE 包裹 5.0", ",".join(str(ipe["parcel"]["5"][z]) for z in Z),
      "7453,7880,9404,9427,10837,12187,14760,18436,7771")

ipf = D["services"]["export"]["IPF"]
dtd = ipf["per_kg"]["DTD"]
check("IPF 大貨 DTD 68-99", ",".join(str(dtd[0]["rate"][z]) for z in Z),
      "444,469,842,861,894,1045,1225,1457,456")
check("IPF 大貨 DTD 1000+", f"{dtd[-1]['from']}-{dtd[-1]['to']}", "1000-99999")

# ---------- 2. 完整性 ----------
print("\n[2] 完整性")
for direction in ("export", "import"):
    for code, svc in D["services"][direction].items():
        if "parcel" in svc:
            ws = sorted(float(k) for k in svc["parcel"])
            gaps = [ws[i] for i in range(1, len(ws)) if round(ws[i] - ws[i - 1], 2) != 0.5]
            print(f"  {direction:6s} {code:4s} 包裹 {ws[0]}~{ws[-1]} 共 {len(ws)} 檔 "
                  f"{'✅ 級距連續' if not gaps else f'❌ 斷點 {gaps[:3]}'}")
            fails += 1 if gaps else 0

# ---------- 3. 服務地區一覽表 ----------
print("\n[3] 服務地區一覽表")
zt = D["zone_table"]
print(f"  共 {len(zt)} 個國家/地區")
MUST = ["中國", "美國", "越南", "日本", "德國", "南非", "香港", "印度"]
for kw in MUST:
    hits = [k for k in zt if kw in k]
    if hits:
        print(f"  ✅ {kw}: {hits[0]} → {zt[hits[0]]}")
    else:
        print(f"  ❌ {kw}: 查無")
        fails += 1

print(f"\n{'='*50}\n{'✅ 全部通過' if fails == 0 else f'❌ 有 {fails} 項不符'}")
sys.exit(1 if fails else 0)
