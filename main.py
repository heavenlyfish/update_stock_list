"""
抓取上市 / 上櫃 / 興櫃 ISIN，合併後貼到
https://docs.google.com/spreadsheets/d/GSHEET_ID (工作表「上市櫃」)
"""
import os, json, requests, pandas as pd
import time
from bs4 import BeautifulSoup, FeatureNotFound
import gspread
import io
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

BASE = "isin.twse.com.tw"

def fetch_twse(mode: int, headers: dict, use_https: bool = True) -> requests.Response:
    scheme = "https" if use_https else "http"
    url = f"{scheme}://{BASE}/isin/C_public.jsp?strMode={mode}"
    return requests.get(url, timeout=30, headers=headers)

def get_isin(mode: int,
             start_mark: str | None = None,
             end_mark: str | None = None,
             max_retry: int = 3,
             backoff: float = 2.0) -> pd.DataFrame:
    headers = {"User-Agent": UA}
    use_https = True            # 先以 HTTPS 嘗試

    for attempt in range(1, max_retry + 1):
        # ① 抓資料（失敗就自動改 HTTP，再重試）
        try:
            r = fetch_twse(mode, headers, use_https=use_https)
        except requests.RequestException as e:
            print(f"[warn] mode={mode} 抓取失敗 ({e}); 改用 HTTP")
            use_https = False
            time.sleep(backoff * attempt)
            continue

        r.encoding = "big5"
        soup = BeautifulSoup(r.text, "lxml")
        table = soup.select_one("table.h4")

        if table:                       # ② 成功抓到 table
            break
        else:
            print(f"[warn] mode={mode} 第 {attempt}/{max_retry} 次抓不到 table.h4")
            if attempt == 1:            # 第一次抓不到就切 HTTP 再試
                use_https = False
            if attempt < max_retry:
                time.sleep(backoff * attempt)
    else:
        # ③ 三次都失敗 → 最後用 read_html 試試
        try:
            df_list = pd.read_html(
                io.StringIO(r.text), header=0, encoding="big5", flavor="lxml"
            )
            if df_list:
                table_html = df_list[0].to_html(index=False)
                table = BeautifulSoup(table_html, "lxml").select_one("table")
        except ValueError:
            table = None

    if not table:
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

    # 取得興櫃（mode=5）
    emg  = get_isin(5)
    if emg.empty:
        print("[warn] 興櫃抓取失敗，將跳過合併")
        emg = pd.DataFrame(columns=["代號", "簡稱", "市場別", "產業別"])

    # 合併三個市場
    return (
        pd.concat([twse, otc, emg], ignore_index=True)
          .drop_duplicates(subset="代號")
          .sort_values("代號")
          .reset_index(drop=True)
    )


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