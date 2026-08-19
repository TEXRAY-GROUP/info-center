DHL 與 FedEx 的對外公告價是**年度版**,新的一年開始後需要手動更新一次。

## 為什麼不做成自動抓取

- FedEx 的 Akamai 會擋 GitHub Actions 機房的 IP(下載到的不是 PDF),在 Actions 裡根本抓不到,必須從**台灣的網路環境**執行。
- 兩家都是一年換一次版,DHL 那份還有 6 MB,沒有每天下載重新解析的必要。

## 更新步驟

1. 確認兩家新版價目表的檔名與生效日:
   - DHL:`https://mydhl.express.dhl/content/dam/downloads/tw/zh/rate-guide/service_and_rate_guide_tw_zh_<年>.pdf.coredownload.pdf`
   - FedEx:`https://www.fedex.com/content/dam/fedex/international/rates/` 底下的 `fedex-rates-exp-zh-tw-<年>.pdf`、`-imp-`、`-zi-` 三份
2. 改 `scripts/parse_dhl_public.py` 與 `scripts/parse_fedex_public.py` 最上方的 `RATE_YEAR`。
   若生效日不是 DHL 1/1、FedEx 1/5,同一區的 `effective` 也要一併調整。
3. 在**台灣的網路環境**本機執行(Windows 記得加 `PYTHONIOENCODING=utf-8`,否則 `⚠` 符號會讓 cp950 主控台崩潰):
   ```
   python scripts/parse_fedex_public.py
   python scripts/fetch_freight.py
   ```
4. 用對帳腳本確認解析結果與 PDF 一致:
   ```
   python scripts/verify_dhl_public.py
   python scripts/verify_fedex_public.py
   ```
5. 確認 `data/freight.json` 的 `effective` 已是新年度,提交該檔與兩支腳本。
6. 執行 `python scripts/check_freight_year.py`,結論變成「仍是當年度版」後關閉本 issue。

## 注意

價目表只放**對外公告價**。談定的合約價一律不進這個 repo(本 repo 為公開),
合約價相關工具放在 `texray-freight-internal`,不對外發佈。
