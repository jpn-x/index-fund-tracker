"""
指数連動ETF・為替の終値データを取得し docs/data/prices.json を更新する。

データソース:
- ETF: Yahoo Finance の公開チャートAPI (query1.finance.yahoo.com)
- 為替(USDJPY): Frankfurter (ECB公式レート, frankfurter.dev)
どちらも無認証・利用規約上の自動取得制限なしで利用できる公開JSON API。

投資信託(基準価額)は、主要データ源(Yahoo!ファイナンス日本版, 投信総合検索
ライブラリー)がいずれも自動取得を禁止/内部トークン認証で保護しているため、
本スクリプトの対象外としている。
"""
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "docs" / "data" / "prices.json"

UA = "Mozilla/5.0 (compatible; index-fund-tracker/1.0)"

# 銘柄マスタ: シンボル, 表示名, カテゴリ, 分類タグ, 通貨
TICKERS = [
    {"symbol": "1321.T", "name": "NEXT FUNDS 日経225 ETF", "category": "domestic", "tag": "日経225 ETF", "currency": "JPY"},
    {"symbol": "1306.T", "name": "NEXT FUNDS TOPIX ETF", "category": "domestic", "tag": "TOPIX ETF", "currency": "JPY"},
    {"symbol": "1489.T", "name": "NEXT FUNDS 日経平均高配当株50 ETF", "category": "domestic", "tag": "高配当", "currency": "JPY"},
    {"symbol": "1478.T", "name": "iシェアーズ MSCIジャパン高配当ETF", "category": "domestic", "tag": "高配当", "currency": "JPY"},
    {"symbol": "1343.T", "name": "NEXT FUNDS 東証REIT ETF", "category": "domestic", "tag": "J-REIT", "currency": "JPY"},
    {"symbol": "VTI", "name": "VTI（バンガード・トータル・ストック・マーケットETF）", "category": "global", "tag": "米国市場全体", "currency": "USD"},
    {"symbol": "VOO", "name": "VOO（バンガード・S&P500 ETF）", "category": "global", "tag": "米国S&P500", "currency": "USD"},
    {"symbol": "VT", "name": "VT（バンガード・トータル・ワールドETF）", "category": "global", "tag": "全世界株", "currency": "USD"},
    {"symbol": "VYM", "name": "VYM（バンガード・米国高配当ETF）", "category": "global", "tag": "米国高配当株", "currency": "USD"},
]

PERIOD1 = 946684800  # 2000-01-01 (各銘柄の上場日より十分前)


def fetch_json(url: str, retries: int = 3) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"fetch failed: {url}") from last_err


def fetch_etf_series(symbol: str) -> dict:
    period2 = int(time.time())
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?period1={PERIOD1}&period2={period2}&interval=1d"
    )
    d = fetch_json(url)
    result = d["chart"]["result"][0]
    timestamps = result["timestamp"]
    closes = result["indicators"]["quote"][0]["close"]
    series = {}
    for ts, close in zip(timestamps, closes):
        if close is None:
            continue
        date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        series[date] = round(float(close), 4)
    return series


def fetch_usdjpy_series() -> dict:
    start = "1999-01-04"
    end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    url = f"https://api.frankfurter.dev/v1/{start}..{end}?base=USD&symbols=JPY"
    d = fetch_json(url)
    return {date: round(float(rates["JPY"]), 4) for date, rates in d["rates"].items()}


def main():
    existing = {}
    if DATA_PATH.exists():
        existing = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    out = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "tickers": TICKERS,
        "prices": {},
        "usdjpy": {},
    }

    for t in TICKERS:
        symbol = t["symbol"]
        try:
            series = fetch_etf_series(symbol)
            print(f"OK  {symbol}: {len(series)} points")
            out["prices"][symbol] = series
        except Exception as e:
            print(f"NG  {symbol}: {e}")
            # 取得失敗時は前回データを維持
            if symbol in existing.get("prices", {}):
                out["prices"][symbol] = existing["prices"][symbol]

    try:
        out["usdjpy"] = fetch_usdjpy_series()
        print(f"OK  USDJPY: {len(out['usdjpy'])} points")
    except Exception as e:
        print(f"NG  USDJPY: {e}")
        out["usdjpy"] = existing.get("usdjpy", {})

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {DATA_PATH}")


if __name__ == "__main__":
    main()
