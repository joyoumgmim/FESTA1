"""
=============================================================
  FESTA 기법 (테스타 매매법) - 분석 로직 모듈 (개선판)
=============================================================
  주요 개선:
  - "신호 발생일" / "신호 시점가" / "현재가" 명확히 구분
  - 신호 후 경과일수 표시
  - 추격매수 위험 경고 (신호 후 가격 변동 추적)
  - "오늘 신호" 여부 별도 플래그
=============================================================
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta


# ------------------------------------------------------------
# 1. 데이터 로드
# ------------------------------------------------------------
def load_stock_data(ticker: str, period: str = "6mo") -> pd.DataFrame:
    """한국 주식 데이터 로드"""
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        return df
    except Exception as e:
        print(f"데이터 로드 실패: {e}")
        return pd.DataFrame()


# ------------------------------------------------------------
# 2. 이동평균선 계산 (5/25/75일)
# ------------------------------------------------------------
def calculate_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['MA5']  = df['Close'].rolling(window=5).mean()
    df['MA25'] = df['Close'].rolling(window=25).mean()
    df['MA75'] = df['Close'].rolling(window=75).mean()
    return df


# ------------------------------------------------------------
# 3. 정배열 + 우상향 판정
# ------------------------------------------------------------
def check_alignment(df: pd.DataFrame, lookback: int = 5) -> pd.DataFrame:
    df = df.copy()
    df['정배열'] = (df['MA5'] > df['MA25']) & (df['MA25'] > df['MA75'])
    df['MA5_상승']  = df['MA5']  > df['MA5'].shift(lookback)
    df['MA25_상승'] = df['MA25'] > df['MA25'].shift(lookback)
    df['MA75_상승'] = df['MA75'] > df['MA75'].shift(lookback)
    df['우상향'] = df['MA5_상승'] & df['MA25_상승'] & df['MA75_상승']
    df['진입가능'] = df['정배열'] & df['우상향']
    return df


# ------------------------------------------------------------
# 4. 매수 신호: 5일선 눌림목 후 재돌파
# ------------------------------------------------------------
def detect_buy_signals(df: pd.DataFrame, vol_mult: float = 1.2) -> pd.DataFrame:
    df = df.copy()
    df['거래량평균20'] = df['Volume'].rolling(20).mean()
    df['거래량증가'] = df['Volume'] >= df['거래량평균20'] * vol_mult
    df['어제_MA5아래'] = df['Close'].shift(1) < df['MA5'].shift(1)
    df['오늘_MA5돌파'] = df['Close'] > df['MA5']
    df['매수신호'] = (
        df['진입가능'] &
        df['어제_MA5아래'] &
        df['오늘_MA5돌파'] &
        df['거래량증가']
    )
    return df


# ------------------------------------------------------------
# 5. 매도 신호
# ------------------------------------------------------------
def detect_sell_signals(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['MA25이탈'] = df['Close'] < df['MA25']
    df['정배열깨짐'] = ~df['정배열']
    df['매도신호'] = df['MA25이탈'] | df['정배열깨짐']
    return df


# ------------------------------------------------------------
# 6. 매매 계획 계산 (개선: 신호일/신호가/현재가 명확히 구분)
# ------------------------------------------------------------
def calculate_trade_plan(df: pd.DataFrame, lookback_low: int = 10,
                         risk_reward: float = 3.0) -> dict:
    """
    가장 최근 매수신호 기준 매매 계획 계산
    - 신호 시점가 vs 현재가 구분
    - 신호 후 경과일수
    - 추격매수 위험 경고
    """
    if df.empty or '매수신호' not in df.columns:
        return {}

    buy_dates = df.index[df['매수신호']]
    if len(buy_dates) == 0:
        return {}

    last_signal_date = buy_dates[-1]
    signal_price = float(df.loc[last_signal_date, 'Close'])
    current_price = float(df['Close'].iloc[-1])
    current_date = df.index[-1]

    # 신호 후 경과일수 (영업일 기준)
    signal_idx = df.index.get_loc(last_signal_date)
    last_idx = len(df) - 1
    days_since_signal = last_idx - signal_idx

    # 오늘 신호 여부
    is_today_signal = (days_since_signal == 0)

    # 신호 후 가격 변동률
    price_change_pct = (current_price - signal_price) / signal_price * 100

    # 손절가 = 신호일 직전 N일 최저가 (전저점)
    start = max(0, signal_idx - lookback_low)
    prev_low = float(df['Low'].iloc[start:signal_idx].min())

    # 익절가 = 신호가 + (신호가 - 손절가) * 손익비
    risk = signal_price - prev_low
    take_profit = signal_price + risk * risk_reward

    # ⚠️ 추격매수 위험 판단
    # - 손절가 이미 이탈 → 매수 금지
    # - 익절가 근접 (80% 이상 도달) → 추격매수 위험
    # - 신호 후 5일 이상 경과 → 타이밍 지남
    chase_warning = []
    if current_price < prev_low:
        chase_warning.append("⛔ 현재가가 이미 손절가 아래 → 매수 금지")
    if current_price >= signal_price + risk * risk_reward * 0.8:
        chase_warning.append("⚠️ 익절가 근접 (목표 80% 도달) → 추격매수 위험")
    if days_since_signal >= 5:
        chase_warning.append(f"⚠️ 신호 후 {days_since_signal}일 경과 → 타이밍 지났을 수 있음")
    if price_change_pct > 5:
        chase_warning.append(f"⚠️ 신호가 대비 +{price_change_pct:.1f}% 상승 → 추격매수 주의")

    # 현재가 기준 매수 시 손익비 재계산
    current_risk = current_price - prev_low
    current_rr = (take_profit - current_price) / current_risk if current_risk > 0 else 0

    return {
        '신호일': last_signal_date.strftime('%Y-%m-%d'),
        '신호시점가': round(signal_price, 2),
        '현재가': round(current_price, 2),
        '경과일수': days_since_signal,
        '오늘신호': is_today_signal,
        '신호후변동률': round(price_change_pct, 2),
        '손절가': round(prev_low, 2),
        '익절가': round(take_profit, 2),
        '리스크(원)': round(risk, 2),
        '손익비': risk_reward,
        '신호가기준_손실률': round((prev_low - signal_price) / signal_price * 100, 2),
        '신호가기준_목표수익률': round((take_profit - signal_price) / signal_price * 100, 2),
        '현재가매수시_손익비': round(current_rr, 2),
        '추격매수경고': chase_warning,
    }


# ------------------------------------------------------------
# 7. 추적 손절매 시뮬레이션
# ------------------------------------------------------------
def trailing_stop_simulation(df: pd.DataFrame, trail_pct: float = 5.0) -> pd.DataFrame:
    df = df.copy()
    df['추적손절가'] = np.nan
    if '매수신호' not in df.columns:
        return df
    buy_dates = df.index[df['매수신호']]
    if len(buy_dates) == 0:
        return df
    last_buy = buy_dates[-1]
    after = df.loc[last_buy:].copy()
    after['신고가'] = after['Close'].cummax()
    after['추적손절가'] = after['신고가'] * (1 - trail_pct / 100)
    df.loc[after.index, '추적손절가'] = after['추적손절가']
    return df


# ------------------------------------------------------------
# 8. 종합 분석 실행
# ------------------------------------------------------------
def analyze(ticker: str, period: str = "6mo",
            vol_mult: float = 1.2, lookback_low: int = 10,
            risk_reward: float = 3.0, trail_pct: float = 5.0) -> dict:
    df = load_stock_data(ticker, period)
    if df.empty:
        return {'success': False, 'message': '데이터 없음'}

    df = calculate_moving_averages(df)
    df = check_alignment(df)
    df = detect_buy_signals(df, vol_mult=vol_mult)
    df = detect_sell_signals(df)
    df = trailing_stop_simulation(df, trail_pct=trail_pct)

    plan = calculate_trade_plan(df, lookback_low=lookback_low,
                                risk_reward=risk_reward)

    last = df.iloc[-1]

    # 상태 판정 (오늘 신호 우선)
    if bool(last['매수신호']):
        status = '🟢 오늘 매수신호 발생!'
    elif bool(last['매도신호']):
        status = '🔴 매도신호 (차트 근거 상실)'
    elif bool(last['진입가능']):
        if plan and plan.get('경과일수', 999) <= 3:
            status = f"🟡 최근 신호({plan['경과일수']}일 전), 관망"
        else:
            status = '🟡 관망 (정배열·우상향, 새 눌림목 대기)'
    else:
        status = '⚪ 회피 (정배열 미충족)'

    return {
        'success': True,
        'ticker': ticker,
        'data': df,
        'plan': plan,
        'status': status,
        'last_close': float(last['Close']),
        'last_date': df.index[-1].strftime('%Y-%m-%d'),
        'is_today_signal': bool(last['매수신호']),
    }


# ------------------------------------------------------------
# 9. 종목 스크리닝
# ------------------------------------------------------------
def screen_stocks(tickers: dict, period: str = "6mo") -> pd.DataFrame:
    results = []
    for name, code in tickers.items():
        res = analyze(code, period=period)
        if not res['success']:
            continue
        row = {
            '종목명': name, '티커': code,
            '현재가': res['last_close'],
            '날짜': res['last_date'], '상태': res['status'],
        }
        if res['plan']:
            row.update({
                '신호일': res['plan'].get('신호일'),
                '신호시점가': res['plan'].get('신호시점가'),
                '경과일': res['plan'].get('경과일수'),
                '손절가': res['plan'].get('손절가'),
                '익절가': res['plan'].get('익절가'),
            })
        results.append(row)
    return pd.DataFrame(results)


# ------------------------------------------------------------
# 10. 포트폴리오 손익 계산 (실제 매수 내역 기반)
# ------------------------------------------------------------
def evaluate_portfolio_position(ticker: str, buy_price: float, quantity: int,
                                buy_date: str = None,
                                period: str = "6mo",
                                trail_pct: float = 5.0) -> dict:
    """
    실제 매수한 포지션의 현재 상태 평가
    - 현재 손익
    - 추적 손절가 도달 여부
    - 차트 근거 상실 여부 (매도 신호)
    """
    df = load_stock_data(ticker, period)
    if df.empty:
        return {'success': False, 'message': '데이터 없음'}

    df = calculate_moving_averages(df)
    df = check_alignment(df)
    df = detect_sell_signals(df)

    current_price = float(df['Close'].iloc[-1])
    current_date = df.index[-1].strftime('%Y-%m-%d')

    # 손익 계산
    profit_per_share = current_price - buy_price
    total_profit = profit_per_share * quantity
    profit_pct = (current_price - buy_price) / buy_price * 100
    invested = buy_price * quantity
    current_value = current_price * quantity

    # 매수일 이후 신고가 → 추적 손절가
    trailing_stop_price = None
    if buy_date:
        try:
            buy_dt = pd.to_datetime(buy_date)
            if buy_dt in df.index:
                after = df.loc[buy_dt:]
            else:
                after = df.loc[df.index >= buy_dt]
            if not after.empty:
                high_after = float(after['Close'].max())
                trailing_stop_price = round(high_after * (1 - trail_pct / 100), 2)
        except Exception:
            pass

    # 매도 신호 여부
    last = df.iloc[-1]
    sell_alert = bool(last['매도신호'])

    # 액션 추천
    actions = []
    if sell_alert:
        actions.append("🔴 차트 근거 상실 (MA25 이탈 또는 정배열 깨짐) → 청산 검토")
    if trailing_stop_price and current_price <= trailing_stop_price:
        actions.append(f"🔴 추적 손절가({trailing_stop_price:,.0f}) 도달 → 청산 검토")
    if profit_pct <= -7:
        actions.append("⚠️ 손실률 -7% 초과 → 손절 룰 점검 필요")
    if not actions:
        actions.append("✅ 보유 유지 (추세 정상)")

    return {
        'success': True,
        'ticker': ticker,
        '매수가': buy_price,
        '수량': quantity,
        '매수일': buy_date or '미입력',
        '현재가': round(current_price, 2),
        '현재일': current_date,
        '주당손익': round(profit_per_share, 2),
        '총손익': round(total_profit, 2),
        '손익률(%)': round(profit_pct, 2),
        '투자금': round(invested, 2),
        '평가금': round(current_value, 2),
        '추적손절가': trailing_stop_price,
        '매도신호': sell_alert,
        '액션': actions,
    }
