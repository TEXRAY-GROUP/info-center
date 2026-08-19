# -*- coding: utf-8 -*-
"""
品牌客戶動態積木 — 抓取器

追蹤國際成衣品牌商的**經營面**消息(財報、庫存、採購、供應鏈、產能移轉),
對代工廠而言是訂單的領先指標。來源:Google News RSS,全部公開資料。
輸出:data/brands.json

作法
  1. 品牌依**總部所在地**固定歸屬洲別(不隨新聞事件地變動)
  2. 每洲、每語言把品牌名用 OR 合併成一次查詢
     ——一個品牌查一次要 30+ 次請求;合併後約 6 次,且品牌歸屬改由標題比對決定
  3. 過濾:必須有經營面詞彙、且不含雜訊詞
     ——品牌新聞九成是新品/聯名/球鞋/代言,對業務沒有用
  4. 同名字詞要個別排除(見 BRANDS 的 exclude)
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
RSS_ZH = ("https://news.google.com/rss/search?q={}"
          "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant")
RSS_EN = ("https://news.google.com/rss/search?q={}"
          "&hl=en-US&gl=US&ceid=US:en")

REGIONS = [
    ("americas", "美洲"),
    ("europe", "歐洲"),
    ("apac", "亞太"),
]

# id, 顯示名, 洲別, 比對用的別名(中英), 個別排除詞
BRANDS = [
    # ---- 美洲 ----
    ("nike", "Nike", "americas", ["Nike", "耐吉", "耐克"], []),
    ("lululemon", "Lululemon", "americas", ["Lululemon", "露露檸檬"], []),
    ("vf", "VF Corp", "americas",
     ["VF Corp", "VF Corporation", "The North Face", "北面", "Vans", "Timberland"], []),
    ("underarmour", "Under Armour", "americas", ["Under Armour", "安德瑪"], []),
    # 「Gap」是常見英文字(pay gap、supply gap),只認公司全稱與中文名
    ("gap", "Gap", "americas", ["Gap Inc", "Gap Inc.", "蓋璞", "Old Navy", "Banana Republic"], []),
    ("levis", "Levi's", "americas", ["Levi Strauss", "Levi's", "李維斯"], []),
    ("pvh", "PVH", "americas", ["PVH", "Calvin Klein", "Tommy Hilfiger", "凱文克萊"], []),
    ("ralphlauren", "Ralph Lauren", "americas", ["Ralph Lauren", "拉夫勞倫"], []),
    ("patagonia", "Patagonia", "americas", ["Patagonia", "巴塔哥尼亞"], []),
    # 「哥倫比亞」是國家名,中文別名不可用;只認 Columbia Sportswear
    ("columbia", "Columbia Sportswear", "americas",
     ["Columbia Sportswear", "哥倫比亞運動服"], ["哥倫比亞總統", "哥倫比亞政府", "哥倫比亞隊"]),

    # ---- 歐洲 ----
    ("adidas", "Adidas", "europe", ["Adidas", "愛迪達", "阿迪達斯"], []),
    ("puma", "Puma", "europe", ["Puma SE", "Puma 財報", "彪馬"], ["美洲獅", "puma concolor"]),
    ("inditex", "Inditex / Zara", "europe", ["Inditex", "Zara"], []),
    ("hm", "H&M", "europe", ["H&M", "H&amp;M", "Hennes & Mauritz"], []),
    ("decathlon", "Decathlon", "europe", ["Decathlon", "迪卡儂"], []),
    ("primark", "Primark", "europe", ["Primark"], []),
    ("hugoboss", "Hugo Boss", "europe", ["Hugo Boss", "雨果博斯"], []),
    ("burberry", "Burberry", "europe", ["Burberry", "巴寶莉", "博柏利"], []),
    # 總部芬蘭、由中國安踏控股,依總部歸歐洲
    ("amer", "Amer Sports", "europe",
     ["Amer Sports", "亞瑪芬", "Salomon", "Arc'teryx", "始祖鳥"], []),

    # ---- 亞太 ----
    ("fastretailing", "Fast Retailing / Uniqlo", "apac",
     ["Fast Retailing", "Uniqlo", "優衣庫", "迅銷"], []),
    ("asics", "Asics", "apac", ["Asics", "亞瑟士"], []),
    ("mizuno", "Mizuno", "apac", ["Mizuno", "美津濃"], []),
    ("descente", "Descente", "apac", ["Descente", "迪桑特"], []),
    ("anta", "Anta", "apac", ["Anta", "安踏"], []),
    ("lining", "Li-Ning", "apac", ["Li-Ning", "李寧"], []),
    # 註冊新加坡、營運中國,依營運總部歸亞太
    ("shein", "Shein", "apac", ["Shein", "希音"], []),
    ("muji", "MUJI", "apac", ["MUJI", "無印良品", "良品計畫"], []),
]

# 經營面詞彙:標題至少要有一個,否則不是業務關心的消息
BUSINESS_ZH = [
    "財報", "財測", "季報", "年報", "營收", "獲利", "毛利", "虧損", "營運",
    "庫存", "去化", "採購", "供應鏈", "訂單", "產能", "代工", "關廠", "撤出",
    "裁員", "展望", "下修", "上修", "財年", "銷售", "市占", "開店", "收店",
    "擴張", "併購", "收購", "執行長", "關稅", "漲價", "調價", "轉單",
]
BUSINESS_EN = [
    "earnings", "revenue", "sales", "guidance", "forecast", "outlook",
    "inventory", "sourcing", "supply chain", "orders", "layoff", "job cuts",
    "quarter", "profit", "margin", "loss", "ceo", "acquisition", "acquires",
    "tariff", "factory", "manufacturing", "stores", "shuts", "closes",
    "price increase", "results",
]

# 雜訊:命中即丟。品牌新聞絕大多數是新品與行銷
NOISE = [
    # 中文
    "聯名", "球鞋", "開箱", "穿搭", "代言", "限量", "發售", "鞋款", "新品",
    "明星", "藝人", "網紅", "折扣", "優惠", "抽獎", "曬圖", "造型", "時尚穿",
    # 英文
    "sneaker", "colorway", "collab", "drops", "release date", "review",
    "deal", "discount", "giveaway", "outfit", "style guide", "best of",
    # 美國大學運動與獎項報導,常帶到品牌名但與經營無關
    "NCAA", "Big Ten", "NIL", "recruit", "awards finalist", "finalists",
    "colorway", "edition", "restock",
    # 同名誤中
    "League of Legends", "Apex Legends", "英雄聯盟",
]

DAYS = 30
PER_REGION = 25          # 每洲上限
PER_BRAND_DAY = 3        # 同一品牌同一天最多幾則(財報日各家轉載會洗版)
TPE = timezone(timedelta(hours=8))
OUT = Path(__file__).resolve().parents[1] / "data" / "brands.json"

TAG = re.compile(r"<([a-zA-Z:]+)[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</\1>", re.S)
SECTIONS = ["日報", "新聞", "產業", "商情", "財經", "股市", "即時", "焦點", "要聞"]


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


def fetch(query: str, lang: str) -> list[dict]:
    url = (RSS_EN if lang == "en" else RSS_ZH).format(urllib.parse.quote(query))
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            xml = r.read().decode("utf-8", "replace")
    except Exception as err:                      # noqa: BLE001 — 單一查詢失敗不該中斷整批
        print(f"    ⚠ 查詢失敗({lang}):{type(err).__name__}", file=sys.stderr)
        return []

    items = []
    for block in re.findall(r"<item>(.*?)</item>", xml, re.S):
        f = {name: html.unescape(val.strip()) for name, val in TAG.findall(block)}
        title = f.get("title", "")
        source = f.get("source", "")
        if source and title.endswith(" - " + source):
            title = title[: -(len(source) + 3)]
        elif not source and " - " in title:
            title, source = title.rsplit(" - ", 1)
        items.append({
            "title": strip_sections(title.strip()),
            "source": source.strip(),
            "link": f.get("link", ""),
            "date": f.get("pubDate", ""),
            "lang": lang,
        })
    return items


def match_brand(title: str):
    """從標題比對出品牌。回傳 (id, 顯示名, 洲別);比對不到就 None"""
    low = title.lower()
    for bid, name, region, aliases, exclude in BRANDS:
        if any(x.lower() in low for x in exclude):
            continue
        if any(a.lower() in low for a in aliases):
            return bid, name, region
    return None


def has_en(title: str, words) -> bool:
    """
    英文一律用單字邊界比對。用子字串會誤判:
    "Glossy" 含 "loss"、"Finish" 含 "fin",都會被當成經營面詞彙。
    中文沒有詞界,維持子字串比對。
    """
    low = title.lower()
    return any(re.search(rf"\b{re.escape(w.lower())}\b", low) for w in words)


def is_relevant(title: str, lang: str) -> bool:
    low = title.lower()
    zh_noise = [n for n in NOISE if re.search(r"[一-鿿]", n)]
    en_noise = [n for n in NOISE if not re.search(r"[一-鿿]", n)]
    if any(n in title for n in zh_noise) or has_en(title, en_noise):
        return False
    if lang == "en":
        return has_en(title, BUSINESS_EN)
    return any(w in title for w in BUSINESS_ZH)


def normalize(title: str) -> str:
    return re.sub(r"[\s\W_]+", "", title.lower())


def main() -> int:
    now = datetime.now(TPE)
    cutoff = now - timedelta(days=DAYS)
    region_names = dict(REGIONS)

    # 每洲、每語言合併成一次查詢
    raw: dict[str, dict] = {}
    for rid, rlabel in REGIONS:
        names = [b for b in BRANDS if b[2] == rid]
        zh_terms, en_terms = [], []
        for _bid, _name, _r, aliases, _ex in names:
            for a in aliases:
                (zh_terms if re.search(r"[一-鿿]", a) else en_terms).append(a)
        for lang, terms in (("zh", zh_terms + en_terms[:6]), ("en", en_terms)):
            if not terms:
                continue
            q = " OR ".join(f'"{t}"' for t in terms[:14])
            got = fetch(q, lang)
            print(f"  {rlabel} / {lang}:{len(got)} 則")
            for it in got:
                raw.setdefault(it["link"], it)

    print(f"  依連結去重後 {len(raw)} 則")

    seen: set[str] = set()
    items = []
    drop_brand = drop_irrelevant = drop_old = drop_dup = 0

    for it in raw.values():
        title = it["title"]
        if not title or not it["link"]:
            continue
        hit = match_brand(title)
        if not hit:
            drop_brand += 1
            continue
        if not is_relevant(title, it["lang"]):
            drop_irrelevant += 1
            continue
        key = normalize(title)
        if key in seen:
            drop_dup += 1
            continue
        try:
            dt = parsedate_to_datetime(it["date"]).astimezone(TPE)
        except (TypeError, ValueError):
            continue
        if dt < cutoff:
            drop_old += 1
            continue
        seen.add(key)
        bid, bname, region = hit
        items.append({
            "title": title,
            "source": it["source"],
            "link": it["link"],
            "date": dt.strftime("%Y-%m-%d %H:%M"),
            "lang": it["lang"],
            "brand": bid,
            "brand_name": bname,
            "region": region,
        })

    items.sort(key=lambda x: x["date"], reverse=True)
    # 先限制「同品牌同一天」的則數,再限制每洲總數。
    # 不先做前者的話,一個財報日就會把整個洲洗版(實測 Amer Sports 單日 19 則)。
    capped, per = [], {rid: 0 for rid, _l in REGIONS}
    per_brand_day: dict[tuple[str, str], int] = {}
    for i in items:
        bd = (i["brand"], i["date"][:10])
        if per_brand_day.get(bd, 0) >= PER_BRAND_DAY:
            continue
        if per[i["region"]] >= PER_REGION:
            continue
        capped.append(i)
        per_brand_day[bd] = per_brand_day.get(bd, 0) + 1
        per[i["region"]] += 1
    items = capped

    print(f"  丟棄:比對不到品牌 {drop_brand}、非經營面 {drop_irrelevant}、"
          f"重複 {drop_dup}、超過 {DAYS} 天 {drop_old}")
    print(f"  保留 {len(items)} 則 " + str({region_names[r]: n for r, n in per.items()}))
    used = {i["brand_name"] for i in items}
    print(f"  出現的品牌({len(used)}):{sorted(used)}")

    out = {
        "block": "brands",
        "title": "品牌客戶動態",
        "source": "Google News(依品牌名彙整,中英文)",
        "fetched_at": now.isoformat(timespec="seconds"),
        "window_days": DAYS,
        "note": "洲別依**品牌總部所在地**固定歸屬,不隨新聞事件發生地變動。"
                "Amer Sports 總部芬蘭(安踏控股)歸歐洲;Shein 營運總部在中國歸亞太。",
        "regions": [{"id": rid, "label": lab} for rid, lab in REGIONS],
        "brands": [{"id": b[0], "name": b[1], "region": b[2]} for b in BRANDS],
        "items": items,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已寫入 {OUT}({OUT.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
