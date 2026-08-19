# TEXRAY 綜合資訊中心

南緯實業內部用的綜合資訊平台。以「積木」方式一塊一塊擴充:匯率、紡織產業新聞、原物料價格、運費參考。

網址:https://texray-group.github.io/info-center/

---

## 目前的積木

| 積木 | 狀態 | 資料來源 | 更新 |
|---|---|---|---|
| 匯率 | ✅ 已上線 | 臺灣銀行牌告匯率(FinMind 開放 API) | 每工作日 09:23、16:47、18:43 |
| 燃油附加費資料 | ✅ 已上線(無畫面) | DHL 官網自動抓 + FedEx 人工維護 | 每工作日 09:23、16:47、18:43 |
| 紡織產業新聞 | 規劃中 | Google News RSS + 產業媒體 | — |
| 原物料價格 | 規劃中 | Yahoo Finance(棉花/原油/天然氣) | — |
| 運費參考 | 規劃中 | 上海航運交易所 SCFI / CCFI | — |

## 運作方式

這是一個**純靜態網站**,沒有後端。資料由 GitHub Actions 定時抓取後 commit 成 JSON,網頁只讀自己的靜態檔:

```
GitHub Actions(每工作日 09:23、16:47、18:43)
   └─ python scripts/fetch_*.py  ──▶  data/*.json  ──▶  commit & push
                                              │
                                     GitHub Pages 靜態網頁載入
```

好處:不受瀏覽器 CORS 限制、外部服務短暫掛掉不影響瀏覽、資料自動累積成歷史。

## 目錄結構

```
index.html                  頁面骨架
assets/css/style.css        樣式(含深淺色主題與企業識別色)
assets/js/app.js            主程式:主題切換、依註冊表載入積木
assets/js/registry.js       ★ 積木註冊表
assets/js/blocks/<id>.js    各積木的畫面
assets/js/lib/              共用工具(格式化、SVG 圖表)
data/<id>.json              各積木的資料(由抓取器產生)
scripts/fetch_<id>.py       各積木的抓取器
.github/workflows/          自動更新排程
```

## 新增一塊積木

1. 寫 `scripts/fetch_<id>.py`,輸出 `data/<id>.json`
2. 寫 `assets/js/blocks/<id>.js`,`export default { render(el, data), meta(data) }`
3. 在 `assets/js/registry.js` 加一筆,`enabled: true`
4. 在 `.github/workflows/update-data.yml` 加一行 `python scripts/fetch_<id>.py`

既有積木完全不用動。

## 本機預覽

```bash
python -m http.server 8080
```

然後開 http://localhost:8080 。(不能直接雙擊 `index.html`,ES 模組與 `fetch` 需要 http 協定。)

## 手動更新資料

```bash
python scripts/fetch_rates.py
python scripts/fetch_fuel.py
```

## data/fuel.json 是什麼

一份只有兩個百分比的小檔(DHL 與 FedEx 當週燃油附加費),沒有畫面,
提供給公司內部工具取用——那些工具不放在這個 repo,
但需要一個能公開讀取的位置取得最新燃油費率。

- DHL 由 `scripts/fetch_fuel.py` 自動抓官網
- **FedEx 官網封鎖程式抓取,數值需人工維護**:改 `data/fuel_manual.json` 裡的 `percent` 與 `as_of`,
  下次排程(或手動執行)就會寫進 `data/fuel.json`

## 注意事項

- **本 repo 為公開 repo,只放外部公開資訊。內部系統資料(Excel、ERP、資料庫)一律不得放入。**
- 匯率主要顯示「現金賣出」;台銀未掛現金牌價的幣別(如南非幣)自動改列「即期賣出」並標註。
- 台銀官網 `rate.bot.com.tw` 有反爬蟲保護、無法直接抓取,故改用 FinMind 開放 API 取得同一份牌告資料。
