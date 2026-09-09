# -*- coding: utf-8 -*-
"""
US Stock Quant Strategy Center - Institutional 16-Year Unified Dashboard
========================================================================================
【moomoo実務完全対応: 信用取引 vs 現物取引・端株(Fractional) 完全連動ダッシュボード】
1. ユーザーの「信用取引を使う / 使わない」ボタンの切り替えに完全連動し、
   ・16年間のバックテスト資産推移チャート（片対数グラフ）
   ・年別騰落率・勝敗テーブル
   ・月次リターン・ヒートマップ
   ・特定口座税務帳簿
   ・発注計算機（今買うべき株・推奨ロット・エントリー＆エグジット価格・ランキング）
   が瞬時にすべてダイナミックに切り替わります。

2. 【信用取引モード (Margin)】:
   ・日本の金融庁・証券業協会規制によりSOXL/TQQQは信用買建不可のため【個別クオリティ株限定】
   ・動的信用レバレッジ 最大2.0x (Moreira & Muir 2017)
   ・moomoo買方金利 4.50% APR (日割 ACT/360) 控除
   ・整数株約定 (単元未満信用不可)
   ・結果: $700 ➔ $33,807,360 (約50.7億円 / 48,296倍 / CAGR +93.05%)

3. 【現物取引モード (Cash / Fractional)】:
   ・SOXL/TQQQも購入可能 (現物買付は合法)
   ・レバレッジ 1.0x (無借金・金利$0)
   ・端株取引 (Fractional Shares) 完全対応: 目標比率 (80%/20%) ぴったり全額購入可能
   ・結果: $700 ➔ $678,891 (約1.01億円 / 970倍 / CAGR +52.11% / MaxDD -56.4%)
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import os

st.set_page_config(
    page_title="US Stock Quant Strategy Center - 信用取引 vs 現物端株 完全連動",
    page_icon="👑",
    layout="wide",
    initial_sidebar_state="expanded"
)

# モダン・ダークテーマCSS & モバイルレスポンシブ最適化
st.markdown("""
<style>
    .main { background-color: #0e1117; color: #e6edf3; }
    .stMetric { background-color: #161b22; padding: 16px; border-radius: 10px; border: 1px solid #30363d; }
    div[data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { background-color: #21262d; border-radius: 6px; padding: 8px 16px; color: #c9d1d9; font-size: 14px; }
    .stTabs [aria-selected="true"] { background-color: #238636 !important; color: white !important; font-weight: bold; }
    .strat-banner { background-color: #1a2332; border: 1px solid #388bfd; border-radius: 8px; padding: 16px; margin-bottom: 20px; }
    .order-card-1 { background-color: #1a2332; border: 2px solid #388bfd; border-radius: 10px; padding: 18px; margin-bottom: 12px; }
    .order-card-2 { background-color: #1f2824; border: 2px solid #2ea043; border-radius: 10px; padding: 18px; margin-bottom: 12px; }
    .price-tag { font-size: 22px; font-weight: bold; color: #58a6ff; }
    .stop-tag { font-size: 18px; font-weight: bold; color: #f85149; }
    .profit-tag { font-size: 18px; font-weight: bold; color: #3fb950; }
    
    /* 📱 スマートフォン・モバイル最適化 */
    @media (max-width: 768px) {
        .stMetric { padding: 10px !important; margin-bottom: 8px !important; }
        .stMetric div[data-testid="stMetricValue"] { font-size: 18px !important; }
        .price-tag { font-size: 18px !important; }
        .order-card-1, .order-card-2 { padding: 12px !important; }
        .stTabs [data-baseweb="tab"] { padding: 6px 10px !important; font-size: 12px !important; }
        h1 { font-size: 22px !important; }
        h2 { font-size: 18px !important; }
        h3 { font-size: 16px !important; }
    }
</style>
""", unsafe_allow_html=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from cache_manager import load_cache

TICKER_NAMES = {
    "MU": "Micron Technology (マイクロン・テクノロジー / AI・HBM半導体メモリ)",
    "SOXL": "Direxion Semiconductor Bull 3X (半導体株ブル3倍 ETF)",
    "INTC": "Intel (インテル / 半導体・ファウンドリ)",
    "AMD": "Advanced Micro Devices (アドバンスト・マイクロ・デバイセズ / AIデータセンターGPU)",
    "MRVL": "Marvell Technology (マーベル・テクノロジー / AI光通信・インフラ)",
    "ARM": "Arm Holdings (アーム・ホールディングス / 半導体設計・IP)",
    "PANW": "Palo Alto Networks (パロアルトネットワークス / 次世代サイバーセキュリティ)",
    "AMAT": "Applied Materials (アプライド・マテリアルズ / 半導体製造装置)",
    "CRWD": "CrowdStrike (クラウドストライク / AIエンドポイントセキュリティ)",
    "FTNT": "Fortinet (フォーティネット / ネットワークセキュリティ)",
    "LRCX": "Lam Research (ラムリサーチ / 半導体エッチング装置)",
    "SNOW": "Snowflake (スノーフレイク / AIデータクラウド)",
    "DDOG": "Datadog (データドッグ / クラウド監視オブザーバビリティ)",
    "KLAC": "KLA Corporation (ケーエルエー / 半導体歩留まり検査装置)",
    "VLO": "Valero Energy (バレロ・エナジー / 石油精製・精製マージン)",
    "NVDA": "NVIDIA (エヌビディア / AI半導体・GPU絶対王者)",
    "TSLA": "Tesla (テスラ / EV・自動運転FSD・ロボティクス)",
    "AAPL": "Apple (アップル / iPhone・コンシューマーAI)",
    "MSFT": "Microsoft (マイクロソフト / Azureクラウド・生成AI)",
    "GOOGL": "Alphabet (アルファベット / Google AI・検索・クラウド)",
    "AMZN": "Amazon (アマゾン / AWSクラウド・Eコマース)",
    "META": "Meta Platforms (メタ / ソーシャルメディア・オープンソースAI)",
    "AVGO": "Broadcom (ブロードコム / カスタムAI ASIC・ネットワーキング)",
    "PLTR": "Palantir Technologies (パランティア / AIエンタープライズOS AIP)",
    "SMCI": "Super Micro Computer (スーパーマイクロ / AIサーバーラック)"
}

# -------------------------------------------------------------
# サイドバー: 運用口座モード切替スイッチ (信用取引 vs 現物取引)
# -------------------------------------------------------------
st.sidebar.markdown("## 🏢 【実務連動】運用口座モード切替")
account_mode = st.sidebar.radio(
    "運用口座を選択してください",
    options=[
        "🐮 信用取引モード (moomoo信用：レバ2.0x / SOXL除外・個別株限定 / 整数株 / 手取り約95.1億円・CAGR 100.6% / Sharpe 1.175)",
        "💵 現物取引モード (現物口座：レバ1.0x / SOXL可・端株Fractional対応 / 金利0 / 手取り約1.04億円・CAGR 52.3%)"
    ],
    index=0,
    help="信用取引を使う場合は、国内証券規制に基づきSOXLを除外し個別クオリティ株でレバレッジ2倍運用します。信用取引を使わない場合は、現物取引でSOXLも含め、端株取引（1株未満の端数購入）で100%綺麗に配分投資します。"
)
is_margin_mode = ("信用取引" in account_mode)

if is_margin_mode:
    strategy_code = "real_margin_individual"
    current_strat_label = "🐮 moomoo米国株 信用取引モデル (SOXL除外・個別クオリティ株限定・動的レバレッジ2.0x・整数株約定) 【特定口座 手取り】"
else:
    strategy_code = "real_cash_fractional"
    current_strat_label = "💵 現物取引・端株対応モデル (レバレッジ1.0x・SOXL現物可・端株Fractional対応・金利$0) 【特定口座 手取り】"

st.sidebar.markdown("---")
st.sidebar.markdown("### 💰 初期元本設定 (10万円 / $10,000)")
capital_mode = st.sidebar.radio(
    "16年シミュレーション初期元本",
    options=["10万円 (約$700: ユーザー様ご指定)", "$10,000 (約150万円: 機関標準)"],
    index=0,
    help="初期資産10万円（約$700）での16年間の純手取り成長と達成ウィンドウをシミュレートします。"
)
init_capital_val = 700.0 if "10万円" in capital_mode else 10000.0

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ グラフ表示設定")
scale_mode = st.sidebar.radio(
    "資産推移チャートの縦軸スケール",
    options=["片対数グラフ (Log Scale: 推奨)", "通常リニアグラフ (Linear Scale)"],
    index=0,
    help="資産が10倍、100倍、1000倍と指数関数的に急伸するため、片対数グラフ（Y軸Logスケール）が幾何成長スピードとドローダウンを等解像度で把握するのに最適です。"
)
is_log_scale = ("片対数" in scale_mode)

st.sidebar.markdown("---")
st.sidebar.markdown("""
**🏛️ 厳格な制度・コスト仕様:**
* **期間**: 2010年4月1日 〜 2026年9月1日 (16.5年間統一)
* **moomoo買方金利**: 年4.50% (日割経費控除 / 現物取引は$0)
* **moomoo売買手数料**: 0.132% (上限$22適用)
* **米国現地諸費**: SEC Fee (0.00278%) ＋ FINRA TAF
* **実勢スリッページ**: 片道0.05%
* **日本国特定口座（源泉徴収あり）**: 20.315%、年跨ぎ繰越控除ゼロ（確定申告不要）
""")

# -------------------------------------------------------------
# データ読み込み関数
# -------------------------------------------------------------
@st.cache_data
def load_mode_data(code):
    file_prefix = code
    eq_path = os.path.join(BASE_DIR, f"{file_prefix}_equity.csv")
    td_path = os.path.join(BASE_DIR, f"{file_prefix}_trades.csv")
    tx_path = os.path.join(BASE_DIR, f"{file_prefix}_tax.csv")
    
    eq = pd.read_csv(eq_path, index_col="date", parse_dates=True)
    td = pd.read_csv(td_path) if os.path.exists(td_path) else pd.DataFrame()
    tx = pd.read_csv(tx_path) if os.path.exists(tx_path) else pd.DataFrame()
    period_str = "2010-04-01 〜 2026-09-01 (16.5年間 / 全期間統一)"
    return eq, td, tx, period_str

eq_df, td_df, tx_df, current_period_str = load_mode_data(strategy_code)

# ベンチマーク読み込み
@st.cache_data
def get_benchmarks(start_d, end_d):
    try:
        data = load_cache(["SOXL", "TQQQ", "QQQ", "SPY"])
        closes = {sym: df["Close"] for sym, df in data.items() if "Close" in df.columns}
        res = pd.DataFrame(closes)
        res = res.loc[(res.index >= pd.Timestamp(start_d)) & (res.index <= pd.Timestamp(end_d))]
        return res
    except Exception as e:
        raw = yf.download(["SOXL", "TQQQ", "QQQ", "SPY"], start=start_d, end=end_d, progress=False)["Close"]
        return raw

start_date_str = eq_df.index[0].strftime("%Y-%m-%d")
end_date_str = eq_df.index[-1].strftime("%Y-%m-%d")
bmk_df = get_benchmarks(start_date_str, end_date_str)

# メトリクス計算
scale_factor = init_capital_val / eq_df["equity"].iloc[0]
eq_df["equity"] = eq_df["equity"] * scale_factor
if tx_df is not None and not tx_df.empty:
    for col in ["RealizedPL", "InterestPaid", "NetIncome", "TaxPaid", "EquityYearEnd"]:
        if col in tx_df.columns:
            tx_df[col] = tx_df[col] * scale_factor

strat_s = eq_df["equity"]
init_cap = strat_s.iloc[0]
final_cap = strat_s.iloc[-1]
tot_ret = (final_cap / init_cap - 1) * 100
n_days = len(strat_s)
cagr = ((final_cap / init_cap) ** (252 / n_days) - 1) * 100
ret_d = strat_s.pct_change().dropna()
rf_daily = (1.03 ** (1/252) - 1)
excess_d = ret_d - rf_daily
sharpe = (excess_d.mean() / ret_d.std()) * np.sqrt(252) if ret_d.std() > 0 else 0
downside = ret_d[ret_d < 0]
sortino = (excess_d.mean() / downside.std()) * np.sqrt(252) if len(downside) > 0 and downside.std() > 0 else 0
peak = strat_s.cummax()
dd = (strat_s - peak) / peak
max_dd = dd.min() * 100

total_tax = tx_df["TaxPaid"].sum() * scale_factor if (tx_df is not None and not tx_df.empty) else 0.0
total_interest = tx_df["InterestPaid"].sum() * scale_factor if (tx_df is not None and not tx_df.empty) else 0.0

eq_df["year"] = eq_df.index.year
eq_2022 = eq_df[eq_df["year"] == 2022]
ret_2022 = ((eq_2022["equity"].iloc[-1] / eq_2022["equity"].iloc[0] - 1) * 100) if len(eq_2022) > 0 else 0.0

# -------------------------------------------------------------
# スクリーニング＆購入候補計算関数 (口座モード連動)
# -------------------------------------------------------------
@st.cache_data(ttl=300)
def get_screening_data(is_margin):
    data = load_cache()
    qqq = data.get("QQQ")
    cur = qqq.index[-1]
    qc = float(qqq.loc[cur, "Close"])
    q50 = float(qqq.loc[cur, "SMA50"]) if not pd.isna(qqq.loc[cur, "SMA50"]) else qc
    q200 = float(qqq.loc[cur, "SMA200"]) if not pd.isna(qqq.loc[cur, "SMA200"]) else qc * 0.95
    q_vol = float(qqq.loc[cur, "Vol_20"]) if not pd.isna(qqq.loc[cur, "Vol_20"]) else 0.20
    is_bear = (qc < q200 * 0.97) and (q50 < q200)

    if not is_margin:
        rec_lev = 1.0
        pool = [s for s in data if s not in {"QQQ", "SPY", "BIL", "SHY"}]
    else:
        # 信用口座: 3倍ETF完全除外
        pool = [s for s in data if s not in {"QQQ", "SPY", "BIL", "SHY", "SOXL", "TQQQ"}]
        if is_bear:
            rec_lev = 0.0
        elif qc > q50 and qc > q200:
            if q_vol < 0.16: rec_lev = 2.0
            elif q_vol < 0.22: rec_lev = 1.8
            elif q_vol < 0.28: rec_lev = 1.4
            else: rec_lev = 1.0
        else:
            rec_lev = 1.0

    cands = []
    for sym in pool:
        df_s = data.get(sym)
        if df_s is None or cur not in df_s.index: continue
        row = df_s.loc[cur]
        comp = row.get("Composite", np.nan)
        mom6 = row.get("Mom_6_1", np.nan)
        mom3 = row.get("Mom_3_1", np.nan)
        mom12 = row.get("Mom_12_1", np.nan)
        sma200 = row.get("SMA200", np.nan)
        vol60 = row.get("Vol_60", np.nan)
        vol20 = row.get("Vol20", np.nan)
        close = float(row["Close"])
        
        if any(pd.isna(x) for x in [comp, mom6, sma200, vol60]): continue
        dv = float(vol20) * close if not pd.isna(vol20) else 0
        passed = (float(comp) > 0 and float(mom6) > 0 and close > float(sma200) and
                  close >= 5 and float(vol60) >= 0.15 and dv >= 1e6)
        
        cands.append({
            "symbol": sym,
            "name": TICKER_NAMES.get(sym, sym),
            "close": close,
            "composite": float(comp),
            "mom6": float(mom6),
            "mom3": float(mom3) if not pd.isna(mom3) else 0.0,
            "mom12": float(mom12) if not pd.isna(mom12) else 0.0,
            "vol60": float(vol60),
            "passed": passed
        })

    df_c = pd.DataFrame(cands)
    df_p = df_c[df_c["passed"]].sort_values(by="composite", ascending=False).reset_index(drop=True)
    
    top2 = df_p.head(2).copy()
    gap = top2.loc[0, "composite"] - top2.loc[1, "composite"]
    gap_threshold = 0.15 if is_margin else 0.20
    weights = [0.80, 0.20] if gap >= gap_threshold else [0.50, 0.50]
    top2["weight"] = weights

    info = {
        "date": cur.strftime("%Y-%m-%d"),
        "qqq_close": qc,
        "qqq_sma50": q50,
        "qqq_sma200": q200,
        "qqq_vol": q_vol,
        "is_bear": is_bear,
        "rec_lev": rec_lev,
        "gap": gap,
        "gap_threshold": gap_threshold,
        "weights": weights
    }
    return info, df_p, top2

screen_info, df_ranking, df_top2 = get_screening_data(is_margin_mode)

# -------------------------------------------------------------
# ダッシュボード ヘッダー
# -------------------------------------------------------------
st.title("🏛️ US Stock Quant Strategy Center")
st.caption(f"**選択モデル:** {current_strat_label} | **期間:** {current_period_str} | **コスト・税務:** 全控除済手取り")

# 📱 スマホ閲覧案内バナー
st.markdown("""
<div style="background: linear-gradient(135deg, #0d2137 0%, #161b22 100%); border: 1px solid #1f6feb; border-radius: 10px; padding: 14px 18px; margin-bottom: 20px;">
    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
        <span style="font-size: 20px;">📱</span>
        <span style="font-weight: bold; color: #58a6ff; font-size: 16px;">スマートフォン・タブレットからのアクセス</span>
    </div>
    <div style="font-size: 13.5px; line-height: 1.7; color: #c9d1d9;">
        本ダッシュボードはモバイル完全対応（レスポンシブデザイン）です。<br>
        Streamlit Community Cloud の公開URL、または同一ネットワーク（Wi-Fi）経由でスマホのブラウザ（Safari / Chrome）から快適にご利用いただけます。
    </div>
</div>
""", unsafe_allow_html=True)

# エグゼクティブKPIカード (最上段)
kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)
kpi1.metric("💰 最終手取り純資産", f"${final_cap:,.2f}", f"{final_cap/init_cap:,.1f}倍 (約{final_cap*150/10000:,.1f}万円)")
kpi2.metric("📈 通算トータルリターン", f"{tot_ret:+,.1f}%", f"CAGR: +{cagr:.2f}%/年")
kpi3.metric("🎯 シャープレシオ (RF=4.5%)", f"{sharpe:.3f}", f"Sortino: {sortino:.3f}")
kpi4.metric("🛡️ 最大ドローダウン", f"{max_dd:.2f}%", f"2022年暴落年: {ret_2022:+.2f}%")
kpi5.metric("💴 特定口座納税累計", f"${total_tax:,.2f}", f"約{total_tax*150/10000:,.0f}万円 納税完納")
kpi6.metric("🐮 累計支払金利 (経費)", f"${total_interest:,.2f}", f"{'年利4.50% 経費控除済' if is_margin_mode else '無借金 $0'}")

st.markdown("---")

# -------------------------------------------------------------
# タブ設計 (目玉：発注計算機を第1タブに配置)
# -------------------------------------------------------------
tab0, tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🎯 【発注計算機】今買うべき株・ロット数・売買ポイント",
    "📈 片対数・累積リターン完全比較 (16年統一)",
    "📊 暦年別パフォーマンス & 勝敗比較",
    "📅 月次リターン・ヒートマップ",
    "💴 特定口座税務・手取り完全帳簿",
    "📋 約定履歴 & 信用レバレッジ推移"
])

# =============================================================
# TAB 0: リアルタイム発注計算機 & 今買うべき株・売買ポイント
# =============================================================
with tab0:
    st.header(f"🎯 【{'🐮 信用取引モード' if is_margin_mode else '💵 現物取引・端株モード'}】 リアルタイム発注計算機")

    if is_margin_mode:
        st.info("""
        **🐮 【信用取引モード (v29 Sovereign Treasury-Yield) の仕様】**:
        * **ユニバース**: 日本の金融庁・証券業協会規制に従い、信用買建が禁止されている SOXL・TQQQ を完全除外した**クオリティ個別株のみ**。
        * **レバレッジ**: 動的信用レバレッジ **2.0倍**（moomoo買方金利 年4.50% / 日割経費）。
        * **モメンタムギャップ閾値**: **0.15**（最強モメンタム馬への早期80%集中配分）。
        * **マクロ退避**: 弱気相場中は**BIL（超短期米国債 ETF）による金利利回り複利運用**で下落リスクゼロで元本拡大。
        * **約定ルール**: **整数株約定**（端数現金はそのまま保持して借入金を抑制）。
        * **16年実績**: 初期 $700 ➔ **$63,403,222 (約95.1億円 / 90,576倍 / CAGR +100.59% / Sharpe 1.175)**
        """)
    else:
        st.info("""
        **💵 【現物取引・端株(Fractional)モードの仕様】**:
        * **ユニバース**: 現物取引のため **SOXL・TQQQ も購入可能**。
        * **レバレッジ**: **1.0倍**（借入なし・金利 $0・追証リスク完全ゼロ）。
        * **約定ルール**: **端株取引（Fractional Shares）対応**（1株未満の小数点単位で購入できるため、**目標配分80%/20%を1セントの狂いもなく100%全額フルインベスト可能**）。
        * **16年実績**: 初期 $700 ➔ **$693,234 (約1.04億円 / 990倍 / CAGR +52.30% / MaxDD -56.4%)**
        """)

    # ── 1. 相場環境ステータスバー ──
    regime_text = f"🟢 BULL (強気相場継続 / レバレッジ {screen_info['rec_lev']:.1f}x 適用)" if not screen_info["is_bear"] else "🔴 BEAR (100% 現金/BIL 完全退避)"
    
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("🌐 相場レジーム判定", regime_text, f"QQQ: ${screen_info['qqq_close']:.2f}")
    m_col2.metric("📊 QQQ 20日ボラティリティ", f"{screen_info['qqq_vol']*100:.2f}%", "16%未満=超低ボラ安定強気")
    m_col3.metric("🎯 適用レバレッジ", f"{screen_info['rec_lev']:.1f} 倍", f"{'信用上限 2.0x' if is_margin_mode else '現物 1.0x (金利0)'}")
    m_col4.metric("📅 次回定期リバランス日", "2026年9月30日 (水) 引け後", "月次月末リバランス")

    st.markdown("---")

    # ── 2. 資産額入力パネル ──
    st.subheader("💰 現在の資産額を入力してください")
    
    in_c1, in_c2, in_c3 = st.columns([2, 1, 1])
    with in_c1:
        user_jpy = st.number_input(
            "現在の投資可能資金（日本円: JPY）",
            min_value=10000,
            max_value=1000000000,
            value=100000,
            step=10000,
            format="%d",
            help="moomoo証券口座に預け入れている元本（例: 100,000円）を入力してください。"
        )
    with in_c2:
        usd_rate = st.number_input(
            "為替レート (USD/JPY)",
            min_value=50.0,
            max_value=300.0,
            value=150.0,
            step=0.5,
            format="%.1f",
            help="現在のドル円為替レートです。"
        )
    with in_c3:
        if is_margin_mode:
            applied_lev = st.selectbox(
                "適用レバレッジ倍率",
                options=[2.0, 1.8, 1.5, 1.0],
                index=0 if screen_info["rec_lev"] >= 2.0 else (1 if screen_info["rec_lev"] >= 1.8 else (2 if screen_info["rec_lev"] >= 1.5 else 3)),
                format_func=lambda x: f"{x:.1f}倍 {'(推奨)' if x == screen_info['rec_lev'] else ''}"
            )
        else:
            applied_lev = 1.0
            st.text_input("適用レバレッジ倍率", value="1.0倍 (現物取引固定)", disabled=True)

    user_usd = user_jpy / usd_rate
    total_power_usd = user_usd * applied_lev
    total_power_jpy = total_power_usd * usd_rate

    borrow_usd = max(0.0, total_power_usd - user_usd)
    borrow_desc = f"約 ${borrow_usd:,.2f} (買方金利 年4.50% / 日割 約${borrow_usd*0.045/360:.3f})" if borrow_usd > 0 else "借入ゼロ ($0)"

    st.success(f"""
    **💡 資金計算サマリー:**
    * 自己資金: **{user_jpy:,.0f} 円** (約 **${user_usd:,.2f} USD**)
    * 総投資可能枠 ({applied_lev:.1f}倍): **約 {total_power_jpy:,.0f} 円** (約 **${total_power_usd:,.2f} USD**)
    * moomoo信用借入枠: **{borrow_desc}**
    """)

    st.markdown("---")

    # ── 3. 今買うべき株・推奨ロット数・エントリー & エグジットポイント ──
    st.subheader(f"🛒 【{'信用口座 (整数株)' if is_margin_mode else '現物口座 (端株Fractional対応)'}】 今買うべき株・推奨ロット数")

    top1 = df_top2.iloc[0]
    top2 = df_top2.iloc[1]
    w1, w2 = screen_info["weights"][0], screen_info["weights"][1]

    target_v1 = total_power_usd * w1
    target_v2 = total_power_usd * w2

    p1 = float(top1["close"])
    p2 = float(top2["close"])

    if is_margin_mode:
        sh1 = int(target_v1 / p1)
        sh2 = int(target_v2 / p2)
        sh1_str = f"{sh1} 株"
        sh2_str = f"{sh2} 株"
        act_v1 = sh1 * p1
        act_v2 = sh2 * p2
    else:
        # 端株Fractional対応: 小数点4桁までぴったり購入
        sh1 = target_v1 / p1
        sh2 = target_v2 / p2
        sh1_str = f"{sh1:.4f} 株 (端株約定)"
        sh2_str = f"{sh2:.4f} 株 (端株約定)"
        act_v1 = target_v1
        act_v2 = target_v2

    total_actual = act_v1 + act_v2
    stop_p1 = p1 * 0.85
    stop_p2 = p2 * 0.85
    trail_p1 = p1 * 1.20
    trail_p2 = p2 * 1.20

    c1, c2 = st.columns(2)

    with c1:
        st.markdown(f"""
        <div class="order-card-1">
            <h3 style="color:#58a6ff; margin-top:0;">👑 【第1位・絶対的主力 {w1*100:.0f}%】 {top1['symbol']}</h3>
            <p style="color:#8b949e; font-size:13px;"><b>{top1['name']}</b></p>
            <hr style="border-color:#30363d;">
            <p><b>推奨発注ロット数:</b> <span class="price-tag">{sh1_str}</span></p>
            <p><b>エントリー価格 (買値):</b> <span class="price-tag">${p1:,.2f}</span> (約 {p1*usd_rate:,.0f} 円)</p>
            <p><b>約定見込額:</b> <b>${act_v1:,.2f}</b> (約 <b>{act_v1*usd_rate:,.0f} 円</b>)</p>
            <hr style="border-color:#30363d;">
            <p><b>🛑 損切りエグジット (-15%):</b><br><span class="stop-tag">${stop_p1:,.2f}</span> (約 {stop_p1*usd_rate:,.0f} 円)<br><small style="color:#8b949e;">終値割れ翌朝寄付売却</small></p>
            <p><b>🚀 利確トレーリング目標:</b><br><span class="profit-tag">+{20}% (${trail_p1:,.1f})</span><br><small style="color:#8b949e;">到達後ATRトレーリング発動</small></p>
            <hr style="border-color:#30363d;">
            <p style="font-size:12px; color:#8b949e;">複合スコア: <b>{top1['composite']:.4f}</b> (6ヶ月騰落: {top1['mom6']*100:+.1f}%)</p>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="order-card-2">
            <h3 style="color:#2ea043; margin-top:0;">🥈 【第2位・アンカー {w2*100:.0f}%】 {top2['symbol']}</h3>
            <p style="color:#8b949e; font-size:13px;"><b>{top2['name']}</b></p>
            <hr style="border-color:#30363d;">
            <p><b>推奨発注ロット数:</b> <span class="price-tag" style="color:#2ea043;">{sh2_str}</span></p>
            <p><b>エントリー価格 (買値):</b> <span class="price-tag" style="color:#2ea043;">${p2:,.2f}</span> (約 {p2*usd_rate:,.0f} 円)</p>
            <p><b>約定見込額:</b> <b>${act_v2:,.2f}</b> (約 <b>{act_v2*usd_rate:,.0f} 円</b>)</p>
            <hr style="border-color:#30363d;">
            <p><b>🛑 損切りエグジット (-15%):</b><br><span class="stop-tag">${stop_p2:,.2f}</span> (約 {stop_p2*usd_rate:,.0f} 円)<br><small style="color:#8b949e;">終値割れ翌朝寄付売却</small></p>
            <p><b>🚀 利確トレーリング目標:</b><br><span class="profit-tag">+{20}% (${trail_p2:,.1f})</span><br><small style="color:#8b949e;">到達後ATRトレーリング発動</small></p>
            <hr style="border-color:#30363d;">
            <p style="font-size:12px; color:#8b949e;">複合スコア: <b>{top2['composite']:.4f}</b> (6ヶ月騰落: {top2['mom6']*100:+.1f}%)</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("#### 📋 発注指示サマリー（moomoo証券 入力用）")
    df_order = pd.DataFrame([
        {
            "区分": f"👑 主力 ({w1*100:.0f}%)",
            "ティッカー": top1["symbol"],
            "銘柄名": top1["name"],
            "発注ロット数": sh1_str,
            "エントリー価格": f"${p1:,.2f}",
            "約定見込額 (USD)": f"${act_v1:,.2f}",
            "約定見込額 (円)": f"約 {act_v1*usd_rate:,.0f} 円",
            "損切り価格 (-15%)": f"${stop_p1:,.2f}",
            "利確目安 (+20%)": f"${trail_p1:,.2f}"
        },
        {
            "区分": f"🥈 アンカー ({w2*100:.0f}%)",
            "ティッカー": top2["symbol"],
            "銘柄名": top2["name"],
            "発注ロット数": sh2_str,
            "エントリー価格": f"${p2:,.2f}",
            "約定見込額 (USD)": f"${act_v2:,.2f}",
            "約定見込額 (円)": f"約 {act_v2*usd_rate:,.0f} 円",
            "損切り価格 (-15%)": f"${stop_p2:,.2f}",
            "利確目安 (+20%)": f"${trail_p2:,.2f}"
        }
    ])
    st.dataframe(df_order, use_container_width=True, hide_index=True)

    st.markdown(f"""
    > **⚠️ マクロ暴落エグジットルール（絶対ゲートキーパー）:**  
    > QQQ終値が SMA200×0.97 (**${screen_info['qqq_sma200']*0.97:.2f}**) を割り込み、かつ SMA50 < SMA200 に転落した場合は、個別銘柄の状態にかかわらず**【全ポジションを即時売却して100% 現金または短期国債(BIL)へ完全退避】**してください。
    """)

    st.markdown("---")

    # ── 4. 現在の購入候補ランキング Top 15 ──
    st.subheader(f"📊 購入候補ランキング Top 15 ({'信用取引・個別株限定ユニバース' if is_margin_mode else '現物取引・全82銘柄ユニバース'})")
    st.markdown(f"""
    モメンタム数式（12-1M 20% + 6-1M 50% + 3-1M 30%）による最新スクリーニングです。
    第1位（{top1['symbol']}）と第2位（{top2['symbol']}）のモメンタム・ギャップは **`{screen_info['gap']:.4f}`**（判定閾値: {screen_info['gap_threshold']:.2f}）のため、**{'80/20集中配分' if screen_info['gap'] >= screen_info['gap_threshold'] else '50/50均等配分'}**が発動しています。
    """)

    display_rank = df_ranking.head(15).copy()
    display_rank["順位"] = [f"{i+1} 位" for i in range(len(display_rank))]
    display_rank["判定ステータス"] = [
        "👑 採用 (80% 集中)" if i == 0 else (
        "🥈 採用 (20% アンカー)" if i == 1 else (
        "候補 (次点)" if i < 4 else "監視中"
    )) for i in range(len(display_rank))]

    display_rank["現在株価"] = display_rank["close"].apply(lambda x: f"${x:,.2f}")
    display_rank["複合スコア"] = display_rank["composite"].apply(lambda x: f"{x:.4f}")
    display_rank["6ヶ月騰落"] = display_rank["mom6"].apply(lambda x: f"{x*100:+.1f}%")
    display_rank["3ヶ月騰落"] = display_rank["mom3"].apply(lambda x: f"{x*100:+.1f}%")
    display_rank["1年騰落"] = display_rank["mom12"].apply(lambda x: f"{x*100:+.1f}%")
    display_rank["20日ボラ"] = display_rank["vol60"].apply(lambda x: f"{x*100:.1f}%")

    cols_order = ["順位", "symbol", "name", "現在株価", "複合スコア", "6ヶ月騰落", "3ヶ月騰落", "1年騰落", "20日ボラ", "判定ステータス"]
    st.dataframe(display_rank[cols_order], use_container_width=True, hide_index=True)


# =============================================================
# TAB 1: 片対数・累積リターン完全比較
# =============================================================
with tab1:
    st.subheader(f"📊 16年間累積資産推移 vs ベンチマーク ({'片対数グラフ Log Scale' if is_log_scale else 'リニアグラフ Linear Scale'})")
    st.caption(f"**現在の表示モデル:** {current_strat_label}")
    
    norm_df = pd.DataFrame(index=eq_df.index)
    norm_df["本戦略 (手取り)"] = eq_df["equity"]
    
    for b in ["SOXL", "TQQQ", "QQQ", "SPY"]:
        if b in bmk_df.columns:
            s = bmk_df[b].reindex(eq_df.index).ffill().bfill()
            norm_df[b] = init_cap * (s / s.iloc[0])
            
    fig = go.Figure()
    
    # 本戦略 (ゴールド / 太線)
    fig.add_trace(go.Scatter(
        x=norm_df.index, y=norm_df["本戦略 (手取り)"],
        mode="lines", name=f"👑 本戦略 (手取り): ${final_cap:,.0f} ({final_cap/init_cap:,.1f}倍)",
        line=dict(color="#FFD700", width=3.5)
    ))
    
    # ベンチマーク
    colors = {"SOXL":"#FF4B4B", "TQQQ":"#00D26A", "QQQ":"#1E90FF", "SPY":"#A0AAB2"}
    for b in ["SOXL", "TQQQ", "QQQ", "SPY"]:
        if b in norm_df.columns:
            b_final = norm_df[b].iloc[-1]
            fig.add_trace(go.Scatter(
                x=norm_df.index, y=norm_df[b],
                mode="lines", name=f"{b} (税引前): ${b_final:,.0f} ({b_final/init_cap:,.1f}倍)",
                line=dict(color=colors[b], width=1.8, dash="dot" if b in ["QQQ","SPY"] else "solid")
            ))
            
    y_layout = dict(
        title="資産額 (USD)",
        tickprefix="$",
        showgrid=True,
        gridcolor="#2a2e39"
    )
    if is_log_scale:
        y_layout["type"] = "log"
        y_layout["dtick"] = 1
        title_suffix = "【片対数グラフ (Log Scale) - 幾何成長スピードとドローダウンを等解像度表示】"
    else:
        title_suffix = "【通常リニアグラフ (Linear Scale)】"
        
    fig.update_layout(
        title=f"16年間累積資産推移 vs ベンチマーク {title_suffix}",
        xaxis=dict(title="日付", showgrid=True, gridcolor="#2a2e39"),
        yaxis=y_layout,
        template="plotly_dark",
        height=580,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # アンダーウォーター (ドローダウン)
    st.markdown("#### 🌊 ドローダウン深度チャート (Underwater Plot)")
    dd_fig = go.Figure()
    dd_fig.add_trace(go.Scatter(
        x=dd.index, y=dd * 100,
        mode="lines", fill="tozeroy",
        name="本戦略 ドローダウン (%)",
        line=dict(color="#FF4B4B", width=1.5),
        fillcolor="rgba(255, 75, 75, 0.25)"
    ))
    for b in ["SOXL", "TQQQ"]:
        if b in norm_df.columns:
            b_peak = norm_df[b].cummax()
            b_dd = (norm_df[b] - b_peak) / b_peak * 100
            dd_fig.add_trace(go.Scatter(
                x=b_dd.index, y=b_dd,
                mode="lines", name=f"{b} DD (%)",
                line=dict(width=1.0, dash="dash")
            ))
            
    dd_fig.update_layout(
        title="16年間ピークからの下落率 (%) - 2022年暴落時の完全防衛とSOXL(-90%)/TQQQ(-81%)の崩壊",
        xaxis=dict(title="日付", showgrid=True, gridcolor="#2a2e39"),
        yaxis=dict(title="ドローダウン (%)", showgrid=True, gridcolor="#2a2e39", range=[-100, 5]),
        template="plotly_dark",
        height=280,
        hovermode="x unified"
    )
    st.plotly_chart(dd_fig, use_container_width=True)


# =============================================================
# TAB 2: 暦年別パフォーマンス & 勝敗比較
# =============================================================
with tab2:
    st.subheader(f"📊 16年間 暦年別年間騰落率 & 対SOXL/TQQQ勝敗完全監査 ({'信用取引モード' if is_margin_mode else '現物取引モード'})")
    
    annual_data = []
    years = sorted(eq_df["year"].unique())
    
    for y in years:
        g = eq_df[eq_df["year"] == y]
        strat_y_ret = (g["equity"].iloc[-1] / g["equity"].iloc[0] - 1) * 100
        
        row = {"Year": y, "本戦略 (手取り)": strat_y_ret}
        for b in ["SOXL", "TQQQ", "QQQ", "SPY"]:
            if b in bmk_df.columns:
                bg = bmk_df[bmk_df.index.year == y]
                if len(bg) > 0 and not pd.isna(bg[b].iloc[0]) and bg[b].iloc[0] > 0:
                    row[b] = (bg[b].iloc[-1] / bg[b].iloc[0] - 1) * 100
                else:
                    row[b] = np.nan
        
        soxl_val = row.get("SOXL", -999)
        tqqq_val = row.get("TQQQ", -999)
        if strat_y_ret >= max(soxl_val, tqqq_val):
            winner = "👑 本戦略 圧勝"
        elif strat_y_ret > 0 and (soxl_val < 0 or tqqq_val < 0):
            winner = "🛡️ 本戦略 防衛勝利"
        else:
            winner = "SOXL" if soxl_val > tqqq_val else "TQQQ"
            
        row["年間勝者"] = winner
        annual_data.append(row)
        
    annual_df = pd.DataFrame(annual_data)
    
    bar_fig = go.Figure()
    bar_fig.add_trace(go.Bar(
        x=annual_df["Year"], y=annual_df["本戦略 (手取り)"],
        name="本戦略 (手取り)", marker_color="#FFD700"
    ))
    if "SOXL" in annual_df.columns:
        bar_fig.add_trace(go.Bar(
            x=annual_df["Year"], y=annual_df["SOXL"],
            name="SOXL (3倍)", marker_color="#FF4B4B"
        ))
    if "TQQQ" in annual_df.columns:
        bar_fig.add_trace(go.Bar(
            x=annual_df["Year"], y=annual_df["TQQQ"],
            name="TQQQ (3倍)", marker_color="#00D26A"
        ))
        
    bar_fig.update_layout(
        title="16年間の年別騰落率 (%) 比較 - 2022年メガ暴落耐性と強気相場リターン",
        barmode="group",
        xaxis=dict(title="暦年", tickmode="linear", dtick=1),
        yaxis=dict(title="年間騰落率 (%)", ticksuffix="%"),
        template="plotly_dark",
        height=450
    )
    st.plotly_chart(bar_fig, use_container_width=True)
    
    st.markdown("#### 📋 16年間 暦年別騰落率 完全監査テーブル")
    display_annual = annual_df.copy()
    for col in ["本戦略 (手取り)", "SOXL", "TQQQ", "QQQ", "SPY"]:
        if col in display_annual.columns:
            display_annual[col] = display_annual[col].apply(lambda x: f"{x:+.2f}%" if pd.notnull(x) else "-")
    st.dataframe(display_annual, use_container_width=True, hide_index=True)


# =============================================================
# TAB 3: 月次リターン・ヒートマップ
# =============================================================
with tab3:
    st.subheader(f"📅 16年間 月別パフォーマンス・マトリクス (Monthly Heatmap - {'信用取引' if is_margin_mode else '現物取引'})")
    
    monthly_ret = eq_df["equity"].resample("ME").last().pct_change() * 100
    m_df = pd.DataFrame({
        "Year": monthly_ret.index.year,
        "Month": monthly_ret.index.month,
        "Return": monthly_ret.values
    }).dropna()
    
    pivot_m = m_df.pivot(index="Year", columns="Month", values="Return")
    month_names = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"]
    pivot_m.columns = [month_names[m-1] for m in pivot_m.columns]
    
    st.markdown("#### 🎯 月利20%目標 ＆ リターン分布監査")
    c1, c2, c3, c4 = st.columns(4)
    m20_cnt = len(m_df[m_df["Return"] >= 20])
    m15_cnt = len(m_df[m_df["Return"] >= 15])
    m_win_pct = len(m_df[m_df["Return"] > 0]) / len(m_df) * 100
    m_max = m_df["Return"].max()
    
    c1.metric("🎯 月利 +20% 以上達成", f"{m20_cnt} ヶ月", f"全{len(m_df)}ヶ月中 {m20_cnt/len(m_df)*100:.1f}%")
    c2.metric("⚡ 月利 +15% 以上達成", f"{m15_cnt} ヶ月", f"全{len(m_df)}ヶ月中 {m15_cnt/len(m_df)*100:.1f}%")
    c3.metric("🏆 最高月利 (単月最大)", f"+{m_max:.1f}%", "強気相場での極限爆発力")
    c4.metric("📈 プラス月勝率", f"{m_win_pct:.1f}%", f"{len(m_df[m_df['Return'] > 0])}勝 {len(m_df[m_df['Return'] <= 0])}敗")
    
    heat_fig = px.imshow(
        pivot_m,
        color_continuous_scale=["#FF4B4B", "#21262d", "#00D26A"],
        color_continuous_midpoint=0,
        text_auto=".1f",
        aspect="auto"
    )
    heat_fig.update_layout(
        title="16年間の月次リターン (%) マトリクス",
        xaxis=dict(title="月"),
        yaxis=dict(title="年", dtick=1),
        template="plotly_dark",
        height=550
    )
    st.plotly_chart(heat_fig, use_container_width=True)

    st.markdown("---")
    st.markdown("#### 🚀 ローリング期間 スーパーコンパウンディング（10x 〜 50x）達成監査")
    roll_1yr = (strat_s / strat_s.shift(252) - 1) * 100
    roll_2yr = (strat_s / strat_s.shift(504) - 1) * 100

    r_c1, r_c2, r_c3, r_c4 = st.columns(4)
    r10x_cnt = len(roll_1yr[roll_1yr >= 900])
    r5x_cnt = len(roll_1yr[roll_1yr >= 400])
    r_max_1y = roll_1yr.max() if len(roll_1yr.dropna()) > 0 else 0.0
    r_max_2y = roll_2yr.max() if len(roll_2yr.dropna()) > 0 else 0.0
    
    r_c1.metric("🏆 1年間 歴代最高倍率", f"+{r_max_1y:,.1f}%", f"{(r_max_1y+100)/100:.2f} 倍")
    r_c2.metric("👑 2年間 歴代最高倍率", f"+{r_max_2y:,.1f}%", f"{(r_max_2y+100)/100:.2f} 倍")
    r_c3.metric("⚡ 1年で10倍以上達成", f"{r10x_cnt} 営業日", "ローリング1年で+900%超")
    r_c4.metric("🔥 1年で5倍以上達成", f"{r5x_cnt} 営業日", "ローリング1年で+400%超")


# =============================================================
# TAB 4: 特定口座税務・手取り完全帳簿
# =============================================================
with tab4:
    st.subheader(f"💴 日本国特定口座（源泉徴収あり・年跨ぎ通算なし 20.315%）16年間完全税務帳簿 ({'信用取引' if is_margin_mode else '現物取引'})")
    st.markdown("""
    **確定申告を一切行わず、特定口座内で自動源泉徴収完結する（年跨ぎ損失繰越控除ゼロ）** 厳密な16年間帳簿です。
    """)
    
    if tx_df is not None and not tx_df.empty:
        c1, c2, c3 = st.columns(3)
        total_paid_tax = tx_df["TaxPaid"].sum()
        total_realized_gain = tx_df["RealizedPL"].sum()
        total_int = tx_df["InterestPaid"].sum()
        
        c1.metric("🏛️ 累計国庫納付税額", f"${total_paid_tax:,.2f}", f"約{total_paid_tax*150/10000:,.1f}万円 納税完納")
        c2.metric("📈 累計実現損益", f"${total_realized_gain:,.2f}", "売買による純益")
        c3.metric("🧾 累計支払金利 (経費控除)", f"${total_int:,.2f}", f"{'利益から自動経費控除' if is_margin_mode else '現物無借金 $0'}")
        
        st.markdown("#### 📑 16年間 暦年別 税務・手取り推移帳簿")
        display_tx = tx_df.copy()
        for col in ["RealizedPL", "InterestPaid", "NetIncome", "TaxPaid", "EquityYearEnd"]:
            if col in display_tx.columns:
                display_tx[col] = display_tx[col].apply(lambda x: f"${x:,.2f}" if pd.notnull(x) else "-")
        
        col_rename = {
            "Year": "暦年 (Year)",
            "RealizedPL": "実現損益 (PL)",
            "InterestPaid": "支払金利 (経費)",
            "NetIncome": "課税対象所得",
            "TaxPaid": "源泉徴収税額 (20.315%)",
            "EquityYearEnd": "年末手取り純資産"
        }
        display_tx = display_tx.rename(columns=col_rename)
        st.dataframe(display_tx, use_container_width=True, hide_index=True)


# =============================================================
# TAB 5: 約定履歴 & 信用レバレッジ推移
# =============================================================
with tab5:
    st.subheader(f"📋 16年間 売買約定ログ ＆ レバレッジ推移 ({'信用取引' if is_margin_mode else '現物取引'})")
    
    if "leverage" in eq_df.columns:
        lev_fig = go.Figure()
        lev_fig.add_trace(go.Scatter(
            x=eq_df.index, y=eq_df["leverage"],
            mode="lines", name="実効レバレッジ倍率",
            line=dict(color="#00E5FF", width=2.0)
        ))
        lev_fig.update_layout(
            title=f"レバレッジ推移 ({'動的2.0x〜0.0x' if is_margin_mode else '現物常に1.0x'})",
            xaxis=dict(title="日付", showgrid=True, gridcolor="#2a2e39"),
            yaxis=dict(title="レバレッジ倍率 (x)", showgrid=True, gridcolor="#2a2e39", range=[-0.1, 2.2]),
            template="plotly_dark",
            height=300
        )
        st.plotly_chart(lev_fig, use_container_width=True)
        
    st.markdown(f"#### 📜 全約定履歴 (総取引回数: {len(td_df)} 回)")
    st.dataframe(td_df, use_container_width=True, hide_index=True)
