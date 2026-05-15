"""
=============================================================
  FESTA 기법 - 한국 주식 분석 웹 대시보드 (Streamlit)
  실행: streamlit run app.py
=============================================================
  v2.0 업데이트:
  - 📱 모바일 반응형 레이아웃 최적화
  - ⏱️ 기본 분석 기간 1년(1y)으로 변경 (75일선 안정화)
  - 🔍 1년 추세 + 6개월 타점 자동 동시 비교
  - 💡 분석 기간 가이드 표시
=============================================================
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from festa_logic import (
    analyze, screen_stocks, evaluate_portfolio_position
)
from stock_list import (
    DEFAULT_STOCKS,
    get_top_volume_stocks,
    load_watchlist,
    normalize_ticker, search_stock_by_name,
)

# ============================================================
# 페이지 설정 (모바일 최적화)
# ============================================================
st.set_page_config(
    page_title="FESTA 주식 분석",
    page_icon="📈",
    layout="centered",  # wide → centered (모바일 친화적)
    initial_sidebar_state="collapsed"  # 모바일은 사이드바 기본 접힘
)

# ============================================================
# 모바일 반응형 CSS
# ============================================================
st.markdown("""
<style>
/* 모바일 최적화 */
@media (max-width: 768px) {
    /* 메인 컨텐츠 패딩 축소 */
    .main .block-container {
        padding-top: 1rem;
        padding-left: 0.5rem;
        padding-right: 0.5rem;
        max-width: 100%;
    }
    /* 헤더 폰트 사이즈 축소 */
    h1 { font-size: 1.5rem !important; }
    h2 { font-size: 1.3rem !important; }
    h3 { font-size: 1.1rem !important; }
    h4 { font-size: 1rem !important; }
    /* 메트릭 카드 폰트 축소 */
    [data-testid="stMetricValue"] { font-size: 1.1rem !important; }
    [data-testid="stMetricLabel"] { font-size: 0.75rem !important; }
    [data-testid="stMetricDelta"] { font-size: 0.75rem !important; }
    /* 테이블 스크롤 부드럽게 */
    .stDataFrame { font-size: 0.75rem; }
    /* 버튼 크기 손가락 친화적 */
    .stButton button {
        min-height: 2.5rem;
        font-size: 0.9rem;
        padding: 0.4rem 0.8rem;
    }
    /* selectbox/text_input 모바일 친화 */
    .stSelectbox label, .stTextInput label {
        font-size: 0.85rem;
    }
}
/* 데스크탑은 약간 넓게 */
@media (min-width: 769px) {
    .main .block-container {
        max-width: 1100px;
        padding-top: 2rem;
    }
}
/* 공통: 메트릭 카드 깔끔하게 */
[data-testid="stMetric"] {
    background-color: rgba(28, 131, 225, 0.05);
    border: 1px solid rgba(28, 131, 225, 0.1);
    padding: 8px;
    border-radius: 6px;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# 모바일 감지 헬퍼 (세션 상태에 저장)
# ============================================================
def is_mobile():
    """간단한 모바일 감지 - 세션에 저장된 값 또는 기본 False"""
    return st.session_state.get('is_mobile', False)


# ============================================================
# 분석 기간 가이드
# ============================================================
PERIOD_GUIDE = {
    "6mo": "🔍 6개월 - 단기 정밀 타점용",
    "1y":  "⭐ 1년 - 권장 기본값",
    "2y":  "📊 2년 - 큰 추세/백테스트용",
    "5y":  "📚 5년 - 장기 사이클용",
}


# ============================================================
# 사이드바
# ============================================================
st.sidebar.title("⚙️ FESTA")

# 모바일 모드 토글
mobile_mode = st.sidebar.checkbox(
    "📱 모바일 모드",
    value=False,
    help="체크하면 차트가 더 작게 표시됩니다"
)
st.session_state['is_mobile'] = mobile_mode

st.sidebar.markdown("---")

mode = st.sidebar.radio(
    "분석 모드",
    [
        "🔥 거래대금 상위 스크리닝",
        "🔍 종목 검색",
        "📊 단일 종목 분석",
        "📖 가이드",
    ]
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🎯 매매 파라미터")

period = st.sidebar.selectbox(
    "분석 기간",
    ["6mo", "1y", "2y", "5y"],
    index=1,  # 기본값 1y로 변경
    format_func=lambda x: PERIOD_GUIDE.get(x, x)
)

with st.sidebar.expander("⚙️ 고급 설정"):
    vol_mult    = st.slider("거래량 배수", 1.0, 3.0, 1.2, 0.1)
    lookback    = st.slider("전저점 기간(일)", 5, 30, 10)
    risk_reward = st.slider("손익비", 1.0, 5.0, 3.0, 0.5)
    trail_pct   = st.slider("추적 손절(%)", 2.0, 15.0, 5.0, 0.5)

st.sidebar.markdown("---")
st.sidebar.caption("⚠️ 학습/참고용\n투자 책임은 본인")


# ============================================================
# 차트 그리기 (모바일 반응형)
# ============================================================
def plot_chart(df: pd.DataFrame, ticker: str, height: int = None):
    if height is None:
        height = 450 if is_mobile() else 700

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.05, row_heights=[0.75, 0.25],
        subplot_titles=(f"{ticker}", "거래량")
    )
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'],
        low=df['Low'], close=df['Close'], name='가격',
        increasing_line_color='red', decreasing_line_color='blue'
    ), row=1, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=df['MA5'],
        line=dict(color='orange', width=1.2), name='MA5'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA25'],
        line=dict(color='green', width=1.2), name='MA25'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA75'],
        line=dict(color='purple', width=1.2), name='MA75'), row=1, col=1)

    buys = df[df['매수신호']]
    if not buys.empty:
        fig.add_trace(go.Scatter(
            x=buys.index, y=buys['Low'] * 0.98, mode='markers',
            marker=dict(symbol='triangle-up', size=12, color='red'),
            name='🟢매수'
        ), row=1, col=1)

    sells = df[df['매도신호']]
    if not sells.empty:
        fig.add_trace(go.Scatter(
            x=sells.index, y=sells['High'] * 1.02, mode='markers',
            marker=dict(symbol='triangle-down', size=10, color='blue'),
            name='🔴매도'
        ), row=1, col=1)

    if '추적손절가' in df.columns and df['추적손절가'].notna().any():
        fig.add_trace(go.Scatter(
            x=df.index, y=df['추적손절가'],
            line=dict(color='red', width=1, dash='dot'),
            name='추적손절'
        ), row=1, col=1)

    colors = ['red' if df['Close'].iloc[i] >= df['Open'].iloc[i] else 'blue'
              for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'],
        marker_color=colors, name='거래량', showlegend=False), row=2, col=1)

    # 모바일에서는 범례를 위로
    legend_config = (
        dict(orientation='h', yanchor='bottom', y=1.02, x=0, font=dict(size=9))
        if is_mobile()
        else dict(orientation='h', yanchor='bottom', y=1.02)
    )

    fig.update_layout(
        height=height,
        xaxis_rangeslider_visible=False,
        hovermode='x unified',
        legend=legend_config,
        margin=dict(l=10, r=10, t=40, b=10) if is_mobile()
              else dict(l=40, r=40, t=60, b=40),
        font=dict(size=10 if is_mobile() else 12),
    )
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    return fig


# ============================================================
# 모바일 반응형 컬럼 헬퍼
# ============================================================
def responsive_columns(num_cols: int):
    """모바일이면 1열, 데스크탑이면 num_cols열"""
    if is_mobile():
        return [st.container() for _ in range(num_cols)]
    return st.columns(num_cols)


# ============================================================
# 분석 결과 렌더링
# ============================================================
def render_analysis_result(res: dict, display_name: str):
    st.markdown(f"### {display_name}")

    is_today = res.get('is_today_signal', False)
    if is_today:
        st.success(f"### 🟢 오늘 매수신호! ({res['last_date']})")
    elif '매도' in res['status']:
        st.error(f"### {res['status']}")
    elif '관망' in res['status']:
        st.warning(f"### {res['status']}")
    else:
        st.info(f"### {res['status']}")

    # 모바일: 1열, PC: 3열
    if is_mobile():
        st.metric("현재가", f"{res['last_close']:,.0f}원")
        st.metric("기준일", res['last_date'])
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("현재가", f"{res['last_close']:,.0f}원")
        c2.metric("기준일", res['last_date'])
        c3.metric("티커", res['ticker'])

    plan = res['plan']
    if not plan:
        st.warning("📭 분석 기간 내 매수신호 없음")
        st.caption("→ 다른 종목 시도 또는 분석 기간 확장")
        return

    st.markdown("---")
    st.markdown("### 🎯 매수신호 정보")

    # 추격매수 경고
    if plan.get('추격매수경고'):
        st.markdown("#### ⚠️ 매수 전 주의")
        for warn in plan['추격매수경고']:
            st.error(warn)

    # 신호 시점 vs 현재 (모바일에서는 세로 배치)
    st.markdown("#### 📍 신호 시점 vs 현재")

    if is_mobile():
        st.markdown("**🕐 신호 발생 시점**")
        st.metric("신호일", plan['신호일'],
                  f"{plan['경과일수']}일 전" if not is_today else "오늘!")
        st.metric("신호 시점가", f"{plan['신호시점가']:,.0f}원")
        st.markdown("**📊 현재**")
        st.metric("현재가", f"{plan['현재가']:,.0f}원",
                  f"{plan['신호후변동률']:+.2f}%")
        if plan.get('현재가매수시_손익비', 0) > 0:
            st.metric("현재가 매수 시 손익비",
                      f"1 : {plan['현재가매수시_손익비']:.2f}")
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**🕐 신호 발생 시점**")
            st.metric("신호일", plan['신호일'],
                      f"{plan['경과일수']}일 전" if not is_today else "오늘!")
            st.metric("신호 시점가", f"{plan['신호시점가']:,.0f}원")
        with col2:
            st.markdown("**📊 현재**")
            st.metric("현재가", f"{plan['현재가']:,.0f}원",
                      f"{plan['신호후변동률']:+.2f}%")
            if plan.get('현재가매수시_손익비', 0) > 0:
                st.metric("현재가 매수 시 손익비",
                          f"1 : {plan['현재가매수시_손익비']:.2f}")

    # 손절/익절 (모바일에서는 세로)
    st.markdown("#### 💰 손절가 / 익절가")
    if is_mobile():
        st.metric("손절가 (전저점)", f"{plan['손절가']:,.0f}원",
                  f"{plan['신호가기준_손실률']}%")
        st.metric("익절가 (손익비 3:1)", f"{plan['익절가']:,.0f}원",
                  f"+{plan['신호가기준_목표수익률']}%")
        st.metric("리스크/주", f"{plan['리스크(원)']:,.0f}원")
    else:
        p1, p2, p3 = st.columns(3)
        p1.metric("손절가 (전저점)", f"{plan['손절가']:,.0f}원",
                  f"{plan['신호가기준_손실률']}%")
        p2.metric("익절가 (손익비 3:1)", f"{plan['익절가']:,.0f}원",
                  f"+{plan['신호가기준_목표수익률']}%")
        p3.metric("리스크/주", f"{plan['리스크(원)']:,.0f}원")

    # 행동 가이드
    st.markdown("#### 💡 행동 가이드")
    if is_today:
        st.success(
            f"✅ **오늘 종가 진입 적정 시점!**\n\n"
            f"- 매수: **{plan['신호시점가']:,.0f}원**\n"
            f"- 손절: **{plan['손절가']:,.0f}원**\n"
            f"- 익절: **{plan['익절가']:,.0f}원**"
        )
    elif plan['추격매수경고']:
        st.warning(f"⚠️ 신호 {plan['경과일수']}일 전 발생 - 새 신호 대기 권장")
    else:
        st.info(f"📌 {plan['경과일수']}일 전 신호 - 보유 중이면 손절가만 참고")

    # 차트
    st.markdown("### 📈 차트")
    fig = plot_chart(res['data'], display_name)
    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# [모드 1] 거래대금 상위 자동 스크리닝
# ============================================================
if mode == "🔥 거래대금 상위 스크리닝":
    st.title("🔥 거래대금 상위 스크리닝")
    st.caption("💡 시장 관심 = 주도주 (테스타 철학)")

    if is_mobile():
        market = st.selectbox("시장", ["KOSPI", "KOSDAQ", "둘 다"])
        top_n = st.number_input("상위 N개", min_value=10, max_value=100, value=20, step=10)
    else:
        col1, col2 = st.columns(2)
        with col1:
            market = st.selectbox("시장", ["KOSPI", "KOSDAQ", "둘 다"])
        with col2:
            top_n = st.number_input("상위 N개", min_value=10, max_value=100, value=30, step=10)

    if st.button("🚀 스크리닝 실행", type="primary", use_container_width=True):
        with st.spinner("거래대금 상위 종목 가져오는 중..."):
            top_stocks = {}
            if market in ["KOSPI", "둘 다"]:
                top_stocks.update(get_top_volume_stocks("KOSPI", top_n))
            if market in ["KOSDAQ", "둘 다"]:
                top_stocks.update(get_top_volume_stocks("KOSDAQ", top_n))

        if not top_stocks:
            st.error("❌ 종목 추출 실패. 'pip install -U finance-datareader' 실행")
        else:
            st.success(f"✅ {len(top_stocks)}개 분석 시작...")
            progress = st.progress(0)
            status_text = st.empty()
            results = []
            today_signals = []

            for idx, (name, code) in enumerate(top_stocks.items()):
                status_text.text(f"({idx+1}/{len(top_stocks)}) {name}")
                progress.progress((idx + 1) / len(top_stocks))
                res = analyze(code, period=period, vol_mult=vol_mult,
                              lookback_low=lookback, risk_reward=risk_reward,
                              trail_pct=trail_pct)
                if not res['success']:
                    continue
                row = {
                    '종목명': name, '티커': code,
                    '현재가': res['last_close'],
                    '상태': res['status'],
                }
                if res['plan']:
                    row.update({
                        '신호일': res['plan'].get('신호일'),
                        '경과일': res['plan'].get('경과일수'),
                        '손절가': res['plan'].get('손절가'),
                        '익절가': res['plan'].get('익절가'),
                    })
                results.append(row)
                if res.get('is_today_signal'):
                    today_signals.append(row)

            status_text.empty()
            progress.empty()

            df_result = pd.DataFrame(results)
            if df_result.empty:
                st.error("분석 결과 없음")
            else:
                st.markdown(f"## 🟢 오늘 매수신호 ({len(today_signals)}개)")
                if today_signals:
                    st.dataframe(pd.DataFrame(today_signals), use_container_width=True, height=300)
                    st.success("☝️ 종가 진입 가능!")
                else:
                    st.info("오늘 매수신호 종목 없음")

                watch = df_result[df_result['상태'].str.contains('관망')]
                st.markdown(f"### 🟡 관망 ({len(watch)}개)")
                if not watch.empty:
                    st.dataframe(watch, use_container_width=True, height=250)

                with st.expander("📋 전체 결과"):
                    st.dataframe(df_result, use_container_width=True)


# ============================================================
# [모드 2] 종목 검색
# ============================================================
elif mode == "🔍 종목 검색":
    st.title("🔍 종목 검색")
    keyword = st.text_input("종목명 키워드", placeholder="예: 삼성, 한미")

    if keyword:
        with st.spinner("검색 중..."):
            results = search_stock_by_name(keyword)

        if not results:
            st.warning("검색 결과 없음")
        else:
            st.markdown(f"### 결과 ({len(results)}개)")
            for name, ticker, market in results:
                with st.container():
                    st.markdown(f"**{name}** ({ticker}) - {market}")
                    cols = st.columns(2)
                    if cols[1].button("📊 분석", key=f"ana_{ticker}", use_container_width=True):
                        with st.spinner(f"{name} 분석 중..."):
                            res = analyze(ticker, period=period, vol_mult=vol_mult,
                                          lookback_low=lookback, risk_reward=risk_reward,
                                          trail_pct=trail_pct)
                        if res['success']:
                            render_analysis_result(res, f"{name} ({ticker})")
                        else:
                            st.error(res['message'])
                    st.markdown("---")


# ============================================================
# [모드 3] 단일 종목 분석 (다중 기간 비교)
# ============================================================
elif mode == "📊 단일 종목 분석":
    st.title("📊 FESTA 분석")
    st.caption(f"⏱️ 분석 기간: **{PERIOD_GUIDE.get(period, period)}**")

    watchlist = load_watchlist()
    all_stocks = {**DEFAULT_STOCKS, **watchlist}

    stock_name = st.selectbox(
        "종목 선택 (또는 직접 입력)",
        ["직접 입력"] + list(all_stocks.keys())
    )

    if stock_name == "직접 입력":
        ticker_input = st.text_input("티커 (예: 005930)", "005930")
        ticker = normalize_ticker(ticker_input)
        display_name = ticker
    else:
        ticker = all_stocks[stock_name]
        display_name = f"{stock_name} ({ticker})"

    # 다중 기간 비교 옵션
    compare_mode = st.checkbox(
        "🔍 1년 추세 + 6개월 타점 동시 비교",
        value=False,
        help="1년 추세로 큰 흐름을 보고, 6개월로 정밀 타점 확인"
    )

    if st.button("🔍 분석 시작", type="primary", use_container_width=True):
        if compare_mode:
            # 다중 기간 비교 분석
            st.markdown("## 📊 다중 기간 비교 분석")

            tab1, tab2 = st.tabs(["⭐ 1년 (큰 추세)", "🔍 6개월 (정밀 타점)"])

            with tab1:
                with st.spinner("1년 분석 중..."):
                    res_1y = analyze(ticker, period="1y", vol_mult=vol_mult,
                                     lookback_low=lookback, risk_reward=risk_reward,
                                     trail_pct=trail_pct)
                if res_1y['success']:
                    st.info("📈 **1년 차트** - 큰 추세 흐름과 75일 이평선 안정성 확인")
                    render_analysis_result(res_1y, display_name)
                else:
                    st.error(res_1y['message'])

            with tab2:
                with st.spinner("6개월 분석 중..."):
                    res_6mo = analyze(ticker, period="6mo", vol_mult=vol_mult,
                                      lookback_low=lookback, risk_reward=risk_reward,
                                      trail_pct=trail_pct)
                if res_6mo['success']:
                    st.info("🎯 **6개월 차트** - 정밀 타점 확인용 (단기 매매)")
                    render_analysis_result(res_6mo, display_name)
                else:
                    st.error(res_6mo['message'])

            # 종합 판단
            if res_1y['success'] and res_6mo['success']:
                st.markdown("---")
                st.markdown("### 🎯 종합 판단")
                today_1y = res_1y.get('is_today_signal')
                today_6mo = res_6mo.get('is_today_signal')

                if today_1y and today_6mo:
                    st.success("🟢🟢 **두 기간 모두 오늘 매수신호!** 강력한 진입 신호입니다.")
                elif today_1y or today_6mo:
                    st.warning("🟡 한 기간만 신호 발생 - 신중하게 판단하세요.")
                elif '회피' in res_1y['status']:
                    st.error("⛔ 1년 차트에서 정배열 미충족 - 매매 회피 권장")
                elif '관망' in res_1y['status'] and '관망' in res_6mo['status']:
                    st.info("🟡 두 기간 모두 관망 상태 - 새 신호 대기")
                else:
                    st.info("📌 일반 상태 - 차트별 신호 참고")

        else:
            # 단일 기간 분석
            with st.spinner(f"{display_name} 분석 중..."):
                res = analyze(ticker, period=period, vol_mult=vol_mult,
                              lookback_low=lookback, risk_reward=risk_reward,
                              trail_pct=trail_pct)
            if not res['success']:
                st.error(f"❌ {res['message']}")
            else:
                render_analysis_result(res, display_name)


# ============================================================
# [모드 4] 가이드
# ============================================================
else:
    st.title("📖 테스타 매매법 가이드")

    st.markdown("""
### 🎯 투자 철학
- **차트로 사면 차트로 판다** - 자기합리화 금지
- **주도주 매매** - 변동성/거래량 있는 종목만
- **확률·기대값** - 손익비 3:1, 손절은 1초 안에

### 📐 매매 규칙
| 항목 | 규칙 |
|---|---|
| 이평선 | 5일/25일/75일 |
| 진입 | 정배열 + 우상향 + 5일선 눌림목 후 재돌파 |
| 손절 | 전저점 |
| 익절 | 손익비 3:1 |
| 매도 | MA25 이탈 또는 정배열 깨짐 |

### ⏱️ 분석 기간 가이드
| 기간 | 용도 |
|---|---|
| 6개월 | 단기 정밀 타점 |
| **1년** ⭐ | **권장 기본값 (75일선 안정)** |
| 2년 | 큰 추세 / 백테스트 |
| 5년 | 장기 사이클 |

### 🟢🟡⚪🔴 신호
| 신호 | 의미 | 행동 |
|---|---|---|
| 🟢 매수신호 | 오늘 신호 발생 | 종가 진입 |
| 🟡 관망 | 정배열·우상향, 타점 대기 | 대기 |
| ⚪ 회피 | 정배열 미충족 | 매매 금지 |
| 🔴 매도신호 | 차트 근거 상실 | 청산 |

### 📱 모바일 사용 팁
- 사이드바 좌상단 **>** 버튼으로 열기
- **📱 모바일 모드** 체크하면 차트 작아짐
- 가로 화면 추천 (차트 보기 편함)

---
⚠️ **면책**: 학습용입니다. 투자 책임은 본인에게 있습니다.
""")
