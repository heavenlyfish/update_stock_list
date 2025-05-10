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