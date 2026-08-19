"""
檢查 data/freight.json 是不是還停在去年的價目表。

DHL 與 FedEx 的對外公告價都是年度版(DHL 1/1、FedEx 1/5 生效),
一年才換一次,而且 FedEx 的 Akamai 會擋 GitHub 機房 IP,無法在 Actions
裡自動抓取——必須有人從台灣的網路環境本機重跑再提交。

所以改用「提醒」而不是「自動更新」:由 freight-annual-check.yml 每月呼叫
這支腳本,發現年度落後就開一張 issue 通知。

本機直接執行也會印出結果,可用來確認邏輯。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

TAIPEI = timezone(timedelta(hours=8))
DATA = Path(__file__).resolve().parents[1] / "data" / "freight.json"


def main() -> int:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    years = sorted({int(data[c]["effective"][:4]) for c in ("dhl", "fedex")})
    now_year = datetime.now(TAIPEI).year
    stale = years[0] < now_year

    print(f"價目表年度:{'/'.join(map(str, years))}")
    print(f"目前年度  :{now_year}")
    print("結論      :" + ("需要更新為新年度版" if stale else "仍是當年度版,無須動作"))

    # 供 workflow 後續步驟判斷
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"stale={'true' if stale else 'false'}\n")
            f.write(f"years={'/'.join(map(str, years))}\n")
            f.write(f"now_year={now_year}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
