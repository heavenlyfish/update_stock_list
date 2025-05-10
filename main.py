"""
抓取上市 / 上櫃 / 興櫃 ISIN，合併後貼到
https://docs.google.com/spreadsheets/d/GSHEET_ID (工作表「上市櫃」)
"""
import os, json, requests, pandas as pd
from bs4 import BeautifulSoup
import gspread
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def get_isin(mode: int,
             start_mark: str | None = None,
             end_mark: str | None = None,
             max_retry: int = 3,
             backoff: float = 2.0) -> pd.DataFrame:
    """
    抓取 TWSE/OTC/興櫃 ISIN。
    若解析失敗，最多 retry `max_retry` 次；最後回傳空 df，
    不讓整支程式崩潰。
    """
    url = f"https://isin.twse.com.tw/isin/C_public.jsp?strMode={mode}"
    headers = {"User-Agent": UA}

    for attempt in range(1, max_retry + 1):
        r = requests.get(url, timeout=30, headers=headers)
        r.encoding = "big5"
        soup = BeautifulSoup(r.text, "lxml")

        table = soup.select_one("table.h4")
        if table:
            break                                   # 解析成功 → 跳出 retry 迴圈
        else:
            print(f"[warn] mode={mode} 第 {attempt}/{max_retry} 次抓不到 table.h4")
            if attempt < max_retry:
                time.sleep(backoff * attempt)       # 指數退避
            else:
                # 最後一次仍失敗：改用 pandas.read_html() 做最後嘗試
                try:
                    df_list = pd.read_html(r.text, header=0, encoding="big5")
                    if df_list:
                        table_html = df_list[0].to_html(index=False)
                        table = BeautifulSoup(table_html, "lxml").select_one("table")
                except ValueError:
                    table = None

    if not table:                                   # 仍失敗 → 回傳空 df
        print(f"[error] mode={mode} 解析失敗，回傳空 DataFrame")
        return pd.DataFrame(columns=["代號", "簡稱", "市場別", "產業別"])

    # ---------- 以下與原本邏輯相同 ----------
    head_tr = next(
        tr for tr in table.find_all("tr")
        if tr.find("td") and tr.find("td").get_text(strip=True).startswith("有價證券代號")
    )
    headers = [td.get_text(strip=True) for td in head_tr.find_all("td")]

    rows, collect = [], start_mark is None
    for tr in head_tr.find_next_siblings("tr"):
        tds = [td.get_text(strip=True) for td in tr.find_all("td")]

        if len(tds) == 1:  # 分類列
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
    if df.empty:
        return pd.DataFrame(columns=["代號", "簡稱", "市場別", "產業別"])

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