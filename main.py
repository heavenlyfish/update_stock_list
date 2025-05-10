"""
抓取上市 / 上櫃 / 興櫃 ISIN，合併後貼到
https://docs.google.com/spreadsheets/d/GSHEET_ID (工作表「上市櫃」)
"""
import os, json, requests, pandas as pd
from bs4 import BeautifulSoup
import gspread
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials


def get_isin(mode: int,
             start_mark: str | None = None,
             end_mark: str | None = None) -> pd.DataFrame:
    url = f"https://isin.twse.com.tw/isin/C_public.jsp?strMode={mode}"
    r = requests.get(url, timeout=30)
    r.encoding = "big5"
    soup = BeautifulSoup(r.text, "lxml")

    table = soup.select_one("table.h4")
    head_tr = next(
        tr for tr in table.find_all("tr")
        if tr.find("td") and tr.find("td").get_text(strip=True).startswith("有價證券代號")
    )
    headers = [td.get_text(strip=True) for td in head_tr.find_all("td")]

    rows, collect = [], start_mark is None
    for tr in head_tr.find_next_siblings("tr"):
        tds = [td.get_text(strip=True) for td in tr.find_all("td")]

        if len(tds) == 1:                     # 分類列
            mark = tds[0]
            if start_mark and mark.startswith(start_mark):
                collect = True
                continue
            if end_mark and mark.startswith(end_mark):
                break
            continue

        if collect and len(tds) == len(headers):
            rows.append(tds)

    df = pd.DataFrame(rows, columns=headers)
    df[["代號", "簡稱"]] = (
        df["有價證券代號及名稱"]
          .str.replace("\u3000", " ", regex=False)
          .str.extract(r"^(\w+)\s+(.*)$")
    )
    return df[["代號", "簡稱", "市場別", "產業別"]]


def crawl_all() -> pd.DataFrame:
    twse = get_isin(2, start_mark="股票", end_mark="上市認購")
    otc  = get_isin(4, start_mark="股票", end_mark="特別股")
    emg  = get_isin(5)

    return (pd.concat([twse, otc, emg], ignore_index=True)
              .drop_duplicates(subset="代號")
              .sort_values("代號")
              .reset_index(drop=True))


def upload_to_gsheet(df: pd.DataFrame):
    gsheet_id = os.getenv("GSHEET_ID")
    if not gsheet_id:
        raise RuntimeError("環境變數 GSHEET_ID 未設定")

    creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    creds = Credentials.from_service_account_info(json.loads(creds_json),
                                                  scopes=[
                                                      "https://www.googleapis.com/auth/spreadsheets",
                                                      "https://www.googleapis.com/auth/drive",
                                                  ])
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(gsheet_id)
    ws = sh.worksheet("上市櫃")                        # 工作表名稱

    ws.clear()                                        # 清空舊資料
    set_with_dataframe(ws, df, include_index=False)  # 從 A1 開始貼


if __name__ == "__main__":

    df_all = crawl_all()
    
    out_dir  = "data"
    os.makedirs(out_dir, exist_ok=True)          # ← 關鍵：自動建資料夾
    out_path = os.path.join(out_dir, "stock_list.csv")

    df_all.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"CSV saved to {out_path}")

    #upload_to_gsheet(df_all)                     # 如果你還要貼 Google Sheets