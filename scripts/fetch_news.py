# -*- coding: utf-8 -*-
"""
紡織產業新聞積木 — 抓取器

來源:Google News RSS(多組關鍵字查詢),全部公開資料。
輸出:data/news.json

處理流程
  1. 五組關鍵字各查一次,每次最多 100 則
  2. 依連結去重,再依標題正規化去重(同一則常被多家轉載)
  3. 過濾:標題要**同時有產業詞與商業詞、且不含雜訊詞**才留下
     ——只靠產業詞會撈進大量明星穿搭與品牌新品;只靠黑名單則永遠列不完。
       同字異義也要處理(紡織娘是昆蟲、木棉花是動漫代理商)
  4. 貼分類標籤供篩選(不影響去留)
  5. 只保留近 N 天、上限 M 則
"""
from __future__ import annotations

import html
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
RSS = "https://news.google.com/rss/search?q={}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"

QUERIES = [
    "紡織",
    "成衣 OR 針織 OR 梭織",
    "機能布 OR 機能性紡織 OR 運動服飾 OR 戶外服飾",
    "聚酯纖維 OR 尼龍 OR 化纖 OR 棉花 價格",
    "紡織 越南 OR 紡織 東南亞 OR 成衣 供應鏈",
]

# 過濾規則:標題必須「有產業詞」且「有商業詞」且「不含雜訊詞」才留下。
# 只靠產業詞會撈進大量明星穿搭、品牌新品、門市折扣;只靠黑名單則永遠列不完。
INDUSTRY = [
    "紡織", "成衣", "針織", "梭織", "布料", "織布", "染整", "纖維", "化纖",
    "聚酯", "尼龍", "嫘縈", "粘膠", "羊毛", "機能布", "紡纖", "製衣",
    # 「棉」單字太寬鬆(木棉花、棉被、棉花糖都會中),只收具體用語
    "棉花", "美棉", "棉價", "棉紗", "棉布", "棉織", "純棉",
]
BUSINESS = [
    "營收", "EPS", "每股", "獲利", "毛利", "財報", "法人", "股價", "股東",
    "訂單", "接單", "產能", "出貨", "放量", "產業", "業者", "廠商", "設廠",
    "擴廠", "投資", "展望", "景氣", "轉型", "布局", "拓銷", "客戶", "商情",
    "價格", "報價", "行情", "關稅", "稅率", "貿易", "出口", "進口", "供應鏈",
    "研發", "專利", "新材料", "永續", "減碳", "碳排", "回收", "再生", "ESG",
]
NOISE = [
    # 誤撈的同名事物與非產業題材
    "紡織娘", "房產", "包租公", "房市", "買房", "建案", "地上權",
    # 時尚/娛樂/零售
    "穿搭", "造型", "代言", "走光", "告別式", "明星", "藝人", "網紅",
    "開箱", "必買", "懶人", "百搭", "折扣", "門市", "週年慶", "推薦",
    "星座", "命理", "食譜", "展覽", "策展",
    "木棉花", "動漫", "周邊商品", "公益", "贈車", "捐款",
]

# 分類標籤:只影響顯示與篩選,不影響去留
CATEGORIES = [
    ("market", "產業動態", [
        "紡織業", "成衣業", "紡織廠", "成衣廠", "製衣", "接單", "訂單", "產能",
        "出貨", "放量", "展望", "景氣", "旺季", "淡季", "轉型", "布局",
        "擴廠", "投資", "設廠", "拓銷"]),
    ("stock", "個股財報", [
        "營收", "EPS", "每股", "獲利", "法人", "股價", "財報", "毛利",
        "股東會", "除息", "漲停", "跌停", "目標價", "紡織股", "紡纖股"]),
    ("material", "原料行情", [
        "棉花", "美棉", "棉價", "紗價", "聚酯", "尼龍", "化纖", "原料",
        "油價", "報價", "行情", "商情", "PTA", "粘膠", "羊毛", "嫘縈"]),
    ("trade", "國際貿易", [
        "關稅", "稅率", "貿易", "供應鏈", "出口", "進口", "越南", "印尼",
        "柬埔寨", "孟加拉", "印度", "歐盟", "反傾銷", "原產地"]),
    ("tech", "技術研發", [
        "機能", "研發", "新材料", "新纖維", "紡織所", "專利", "智慧紡織",
        "自動化"]),
    ("green", "永續環保", [
        "永續", "減碳", "碳排", "回收", "再生", "環保", "ESG", "循環經濟",
        "生物基"]),
]

DAYS = 30          # 只保留近 30 天
LIMIT = 80         # 上限 80 則
TPE = timezone(timedelta(hours=8))
OUT = Path(__file__).resolve().parents[1] / "data" / "news.json"

TAG = re.compile(r"<([a-zA-Z:]+)[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</\1>", re.S)


def fetch_query(q: str) -> list[dict]:
    url = RSS.format(urllib.parse.quote(q))
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        xml = r.read().decode("utf-8", "replace")

    items = []
    for block in re.findall(r"<item>(.*?)</item>", xml, re.S):
        fields = {name: html.unescape(val.strip()) for name, val in TAG.findall(block)}
        title = fields.get("title", "")
        # Google News 的標題結尾是「 - 媒體名」;<source> 標籤帶屬性,另外抓。
        # 兩者都要處理:有 source 時把結尾那段媒體名去掉,沒有時就從標題拆。
        source = fields.get("source", "")
        if source and title.endswith(" - " + source):
            title = title[: -(len(source) + 3)]
        elif not source and " - " in title:
            title, source = title.rsplit(" - ", 1)
        items.append({
            "title": strip_sections(title.strip()),
            "source": source.strip(),
            "link": fields.get("link", ""),
            "date": fields.get("pubDate", ""),
        })
    return items


# 報社版面名,常黏在標題結尾(如「…前景可期- 日報」「…| 熱門亮點 | 商情」)
SECTIONS = ["日報", "新聞", "產業", "商情", "熱門亮點", "財經", "股市",
            "即時", "專欄", "焦點", "要聞", "頭條"]


def strip_sections(title: str) -> str:
    changed = True
    while changed:
        changed = False
        for sep in ("|", "-", "－", "—"):
            idx = title.rfind(sep)
            if idx > 0 and title[idx + 1:].strip() in SECTIONS:
                title = title[:idx].strip()
                changed = True
    return title


def normalize(title: str) -> str:
    """去掉標點與空白,用來辨識轉載重複"""
    return re.sub(r"[\s\W_]+", "", title)


def classify(title: str) -> list[str]:
    return [cid for cid, _label, words in CATEGORIES if any(w in title for w in words)]


def is_relevant(title: str) -> bool:
    """產業詞 + 商業詞 + 無雜訊詞"""
    if any(n in title for n in NOISE):
        return False
    return any(w in title for w in INDUSTRY) and any(w in title for w in BUSINESS)


def main() -> int:
    now = datetime.now(TPE)
    cutoff = now - timedelta(days=DAYS)

    raw: dict[str, dict] = {}
    for q in QUERIES:
        got = fetch_query(q)
        print(f"  查詢「{q[:24]}」 {len(got)} 則")
        for it in got:
            raw.setdefault(it["link"], it)
    print(f"  依連結去重後 {len(raw)} 則")

    seen_titles: set[str] = set()
    items = []
    dropped_noise = dropped_old = dropped_dup = 0

    for it in raw.values():
        title = it["title"]
        if not title or not it["link"]:
            continue
        if not is_relevant(title):
            dropped_noise += 1
            continue
        cats = classify(title) or ["market"]
        key = normalize(title)
        if key in seen_titles:
            dropped_dup += 1
            continue
        try:
            dt = parsedate_to_datetime(it["date"]).astimezone(TPE)
        except (TypeError, ValueError):
            continue
        if dt < cutoff:
            dropped_old += 1
            continue
        seen_titles.add(key)
        items.append({
            "title": title,
            "source": it["source"],
            "link": it["link"],
            "date": dt.strftime("%Y-%m-%d %H:%M"),
            "cats": cats,
        })

    items.sort(key=lambda x: x["date"], reverse=True)
    items = items[:LIMIT]

    print(f"  丟棄:不相關 {dropped_noise}、標題重複 {dropped_dup}、"
          f"超過 {DAYS} 天 {dropped_old}")
    print(f"  保留 {len(items)} 則")
    counts = {cid: sum(1 for i in items if cid in i["cats"]) for cid, _l, _w in CATEGORIES}
    print("  分類分佈:", {label: counts[cid] for cid, label, _w in CATEGORIES})

    out = {
        "block": "news",
        "title": "紡織產業新聞",
        "source": "Google News(多組關鍵字彙整)",
        "fetched_at": now.isoformat(timespec="seconds"),
        "window_days": DAYS,
        "categories": [{"id": cid, "label": label} for cid, label, _w in CATEGORIES],
        "items": items,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已寫入 {OUT}({OUT.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
