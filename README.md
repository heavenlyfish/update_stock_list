# update_stock_list

> **Weekly, end-to-end update of Taiwan‐listed securities (_ISIN_) + stock-futures symbols  
> – from TWSE / OTC / Emerging markets to CSV & Google Sheet, fully automated via GitHub Actions + Google Apps Script.**

---

## ✨ What it does

| Stage | Tool | Result |
|-------|------|--------|
| **1. Crawl ISIN** (上市 / 上櫃 / 興櫃) | `python main.py` on GitHub Actions | `data/stock_list.csv` UTF-8 (bot-committed)<br>Optional: sync to Google Sheet 〈上市櫃〉 |
| **2. Crawl Taifex stock-futures list** | Google Apps Script | Write ⬇ to Sheet 〈股期表〉 A:B |
| **3. Copy codes to analysis sheets** | Google Apps Script | Sync 股期表 A2↓ →<br>可重複_4條件 (D) / 可重複_3條件 (C) / 可重複_2條件 (B) / 可重複 (E) |

Schedules  
* **GitHub Actions** – Every **Friday 09:00 (GMT+8)**  
* **Google Apps Script** – Every **Monday 09:00 (GMT+8)**  

---

## 🗺️ Repository layout

---

## ①  GitHub Actions – weekly ISIN workflow

### Secrets required

| Secret key | Value |
|------------|-------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Entire JSON key string of a Google Service Account **with editing permission on the target Sheet** |
| `GSHEET_ID` | Sheet ID (e.g. `1ztPS-fXH0zQn-8jSleTTFYv1NgoC10_RdSBFQNxXWEM`) |

### How it works

1. `actions/setup-python` → pip upgrade → install deps  
2. Run **`python main.py`**  
   * HTTPS ➜ HTTP fallback, 3× retry, Big5 decoding  
   * Empty DataFrame returned if Emerging (興櫃) is geo-blocked   
   * Outputs **`data/stock_list.csv`**
3. **`git add -f data/stock_list.csv`**  
   * Only in CI (kept ignored locally)  
4. If diff → bot commit & push  
5. _(Optional)_ upload the same DataFrame to Sheet 〈上市櫃〉

> **Cron:** `0 1 * * 5`  → Fri 01:00 UTC = Fri 09:00 Taipei

---

## ②  Google Apps Script – Taifex stock-futures sync

* `updateTaifexSheets()` fetches <https://www.taifex.com.tw/cht/2/stockLists>
* Writes `[code,name]` to Sheet 〈股期表〉 A1:B… (overwrites old)
* Copies **A2↓** to four target sheets/columns, **only if header cell equals “股期代號(自動更新)”**

```text
可重複_4條件  – D 列
可重複_3條件  – C 列
可重複_2條件  – B 列
可重複        – E 列

