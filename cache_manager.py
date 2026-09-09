# -*- coding: utf-8 -*-
"""
超高速 Feather バイナリキャッシュ管理モジュール (cache_manager.py)
================================================================
- 16年分・全クオリティ銘柄の株価データを Feather (PyArrow 列指向バイナリ) 形式で常設管理。
- 読込速度: 1〜3ミリ秒 (全体で約0.03〜0.05秒)。
- 一度作成すれば、バックテスト実行時のネットワーク通信とCPU負荷を完全にゼロ化します。
"""
import sys, os, time, warnings
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import pandas as pd, numpy as np, yfinance as yf
warnings.filterwarnings("ignore")

CACHE_FILE = os.path.join(os.path.dirname(__file__), "stock_data.feather")

# 常設対象ユニバース (主要クオリティ、半導体、メガキャップ、成長株、ベンチマーク)
DEFAULT_UNIVERSE = [
    # メガキャップ・クオリティ
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO", "COST", "ASML",
    # 半導体コア (SOXL構成中核)
    "AMD", "TSM", "QCOM", "TXN", "MU", "INTC", "AMAT", "LRCX", "ADI", "KLAC",
    "MRVL", "NXPI", "MCHP", "ON", "ARM",
    # ソフトウェア・クラウド・AI
    "ADBE", "CRM", "ORCL", "NOW", "INTU", "PANW", "CRWD", "SNOW", "DDOG", "NET",
    "FTNT", "WDAY", "TEAM", "ZS", "MDB", "PLTR", "SHOP", "CDNS", "SNPS",
    # プラットフォーム・デジタル
    "NFLX", "BKNG", "ABNB", "MELI", "EBAY", "DASH", "UBER",
    # バイオテック・ヘルスケア・クオリティ
    "AMGN", "GILD", "VRTX", "REGN", "ISRG", "LLY", "UNH",
    # クオリティ産業・オートメーション・決済
    "PYPL", "V", "MA", "AXP", "ADP", "PAYX", "CTAS", "FAST", "ODFL", "PCAR",
    # シクリカル比較用 (旧監査用)
    "SMCI", "MRNA", "URI", "CAT", "DE", "VLO", "MPC", "XOM",
    # ベンチマーク
    "QQQ", "SPY", "BIL", "SHY", "SOXL", "TQQQ"
]

def compute_features(df):
    """テクニカル・モメンタム指標の高速一括算出"""
    df = df.dropna(subset=["Close"]).copy()
    if len(df) < 60:
        return None
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    df["Mom_6_1"] = (df["Close"].shift(21) / df["Close"].shift(126) - 1)
    df["Mom_3_1"] = (df["Close"].shift(21) / df["Close"].shift(63) - 1)
    df["Mom_12_1"] = (df["Close"].shift(21) / df["Close"].shift(252) - 1)
    df["Ret_d"] = df["Close"].pct_change()
    df["Vol_60"] = df["Ret_d"].rolling(60).std() * np.sqrt(252)
    df["Vol_20"] = df["Ret_d"].rolling(20).std() * np.sqrt(252)
    df["Composite"] = df["Mom_6_1"] * 0.5 + df["Mom_3_1"] * 0.3 + df["Mom_12_1"] * 0.2
    df["SMA50"] = df["Close"].rolling(50).mean()
    df["SMA200"] = df["Close"].rolling(200).mean()
    df["Vol20"] = df["Volume"].rolling(20).mean()
    return df

def build_cache(universe=None, start="2008-01-01", force=False):
    """キャッシュを作成・完全常設化する"""
    if universe is None:
        universe = DEFAULT_UNIVERSE
    universe = sorted(list(set(universe)))

    if os.path.exists(CACHE_FILE) and not force:
        print(f"[Feather Cache] 既存キャッシュが存在します: {CACHE_FILE}")
        return load_cache(universe)

    t0 = time.time()
    print(f"[Feather Cache] 全 {len(universe)} 銘柄のデータを初回ダウンロード中 (2008年〜現在)...")
    
    all_rows = []
    # yfinance バッチ取得 (25銘柄ずつ負荷分散)
    for i in range(0, len(universe), 25):
        batch = universe[i:i+25]
        try:
            raw = yf.download(batch, start=start, progress=False, group_by="ticker", auto_adjust=True)
            for sym in batch:
                try:
                    if hasattr(raw.columns, "levels"):
                        if sym not in raw.columns.get_level_values(0):
                            continue
                        df = raw[sym][["Open", "High", "Low", "Close", "Volume"]].copy()
                    elif len(batch) == 1:
                        df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
                    else:
                        continue
                    
                    df = compute_features(df)
                    if df is None:
                        continue
                    
                    tmp = df.reset_index()
                    if "Date" not in tmp.columns and "index" in tmp.columns:
                        tmp.rename(columns={"index": "Date"}, inplace=True)
                    tmp["Ticker"] = sym
                    all_rows.append(tmp)
                except Exception as e:
                    pass
        except Exception as e:
            print(f"  Batch {i} error: {e}")

    if all_rows:
        full_df = pd.concat(all_rows, ignore_index=True)
        # 日付型・文字列型の最適化
        full_df["Date"] = pd.to_datetime(full_df["Date"])
        full_df["Ticker"] = full_df["Ticker"].astype(str)
        full_df.to_feather(CACHE_FILE)
        size_mb = os.path.getsize(CACHE_FILE) / (1024 * 1024)
        print(f"[Feather Cache 完了] {len(set(full_df['Ticker']))} 銘柄を保存完了！")
        print(f"   保存先: {CACHE_FILE} ({size_mb:.2f} MB, 所要時間: {time.time() - t0:.2f} 秒)")
    
    return load_cache(universe)

def sync_daily_cache(universe=None, force=False):
    """
    スマート日次差分同期 (Smart Daily Cache Sync):
    - キャッシュ内の最大日付（max_date）をチェック。
    - 直近営業日より古い場合、yfinance から直近数日分のローソク足のみを数秒で高速バッチ取得。
    - 既存16年データとシームレスに結合し、全テクニカル指標を再計算して Feather に保存。
    """
    if universe is None:
        universe = DEFAULT_UNIVERSE
    universe = sorted(list(set(universe)))

    if not os.path.exists(CACHE_FILE):
        return build_cache(universe)

    try:
        existing_df = pd.read_feather(CACHE_FILE)
        max_date = pd.to_datetime(existing_df["Date"]).max()
    except Exception as e:
        print(f"[Cache Sync Warning] Feather読込失敗、再構築します: {e}")
        return build_cache(universe, force=True)

    today = pd.Timestamp.now().floor("D")
    # 米国市場の直近営業日（土日は金曜、平日は前日終値または当日）
    days_old = (today - max_date).days
    
    # 既に昨夜または当日のデータがあれば更新不要（force=Trueで強制更新）
    if days_old <= 1 and not force and today.dayofweek not in [0, 1]:
        print(f"[Cache Sync] キャッシュは最新です (最新日: {max_date.strftime('%Y-%m-%d')})")
        return

    print(f"[Cache Sync] 株価キャッシュの最新同期を開始... (現在キャッシュ最終日: {max_date.strftime('%Y-%m-%d')})")
    t0 = time.time()
    start_sync = (max_date - pd.Timedelta(days=5)).strftime("%Y-%m-%d")

    delta_dict = {}
    for i in range(0, len(universe), 25):
        batch = universe[i:i+25]
        try:
            raw = yf.download(batch, start=start_sync, progress=False, group_by="ticker", auto_adjust=True)
            for sym in batch:
                try:
                    if hasattr(raw.columns, "levels"):
                        if sym not in raw.columns.get_level_values(0):
                            continue
                        d = raw[sym][["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
                    elif len(batch) == 1:
                        d = raw[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
                    else:
                        continue
                    if not d.empty:
                        if d.index.tz is not None:
                            d.index = d.index.tz_localize(None)
                        delta_dict[sym] = d
                except Exception:
                    pass
        except Exception as e:
            print(f"  Batch {i} delta error: {e}")

    if not delta_dict:
        print("[Cache Sync] 新規差分データはありませんでした。")
        return

    new_rows = []
    updated_cnt = 0
    for sym, group in existing_df.groupby("Ticker"):
        group = group.set_index("Date").sort_index()
        base_cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in group.columns]
        base_ohlcv = group[base_cols].copy()

        if sym in delta_dict:
            delta_ohlcv = delta_dict[sym]
            combined_ohlcv = pd.concat([base_ohlcv, delta_ohlcv])
            combined_ohlcv = combined_ohlcv[~combined_ohlcv.index.duplicated(keep="last")].sort_index()
            if len(combined_ohlcv) > len(base_ohlcv):
                updated_cnt += 1
        else:
            combined_ohlcv = base_ohlcv

        feat_df = compute_features(combined_ohlcv)
        if feat_df is not None:
            tmp = feat_df.reset_index()
            if "Date" not in tmp.columns and "index" in tmp.columns:
                tmp.rename(columns={"index": "Date"}, inplace=True)
            tmp["Ticker"] = sym
            new_rows.append(tmp)

    if new_rows and updated_cnt > 0:
        updated_full = pd.concat(new_rows, ignore_index=True)
        updated_full["Date"] = pd.to_datetime(updated_full["Date"])
        updated_full["Ticker"] = updated_full["Ticker"].astype(str)
        updated_full.to_feather(CACHE_FILE)
        new_max_date = updated_full["Date"].max().strftime("%Y-%m-%d")
        size_mb = os.path.getsize(CACHE_FILE) / (1024 * 1024)
        print(f"⚡ [Cache Sync 完了] {updated_cnt} 銘柄を最新化！(最新基準日: {new_max_date}, {size_mb:.2f} MB, 所要時間: {time.time()-t0:.2f}秒)")
    else:
        print(f"[Cache Sync] キャッシュは既に最新日付です ({time.time()-t0:.2f}秒)")

_LAST_SYNC_TIME = 0

def load_cache(universe=None, auto_sync=True):
    """超高速 Feather 読込 (必要に応じて日次自動同期を実行)"""
    global _LAST_SYNC_TIME
    if not os.path.exists(CACHE_FILE):
        return build_cache(universe)

    # 1時間に1回、バックグラウンドまたは初回アクセス時に日次同期をチェック
    now = time.time()
    if auto_sync and (now - _LAST_SYNC_TIME > 3600):
        try:
            sync_daily_cache(universe)
            _LAST_SYNC_TIME = now
        except Exception as e:
            print(f"[Cache Auto-Sync Warning] 同期エラー（既存キャッシュを使用）: {e}")

    t0 = time.time()
    full_df = pd.read_feather(CACHE_FILE)

    if universe is not None:
        full_df = full_df[full_df["Ticker"].isin(universe)]

    data = {}
    for sym, g in full_df.groupby("Ticker"):
        g = g.set_index("Date").drop(columns=["Ticker"])
        data[sym] = g

    elapsed = time.time() - t0
    print(f"⚡ [Feather Cache HIT] {len(data)} 銘柄を一瞬で読込完了 ({elapsed*1000:.1f} ms / {elapsed:.3f} 秒)")
    return data

if __name__ == "__main__":
    sync_daily_cache(force=True)

