"""
=============================================================
  FESTA - 종목 리스트 관리 모듈
=============================================================
  3가지 종목 소스 제공:
  1) 거래대금 상위 자동 추출 (테스타 철학: 시장 관심 = 주도주)
  2) 사용자 관심종목 (직접 추가/편집)
  3) 기본 대표종목 (오프라인 fallback)
=============================================================
"""

import json
import os
from datetime import datetime, timedelta
import pandas as pd

# 사용자 관심종목 저장 파일
WATCHLIST_FILE = "watchlist.json"

# ------------------------------------------------------------
# 기본 대표 종목 (오프라인 fallback)
# ------------------------------------------------------------
DEFAULT_STOCKS = {
    "삼성전자":       "005930.KS",
    "SK하이닉스":     "000660.KS",
    "LG에너지솔루션": "373220.KS",
    "현대차":         "005380.KS",
    "기아":           "000270.KS",
    "POSCO홀딩스":    "005490.KS",
    "NAVER":          "035420.KS",
    "카카오":         "035720.KS",
    "셀트리온":       "068270.KS",
    "삼성바이오로직스": "207940.KS",
    "에코프로":       "086520.KQ",
    "에코프로비엠":   "247540.KQ",
    "알테오젠":       "196170.KQ",
    "HLB":            "028300.KQ",
    "리노공업":       "058470.KQ",
}


# ------------------------------------------------------------
# 1. 거래대금 상위 종목 자동 추출 (테스타 주도주 철학)
# ------------------------------------------------------------
def get_top_volume_stocks(market: str = "KOSPI", top_n: int = 30) -> dict:
    """
    FinanceDataReader로 거래대금 상위 종목 자동 추출
    (시장의 관심이 쏠린 주도주 = 테스타 매매 대상)

    :param market: 'KOSPI' 또는 'KOSDAQ'
    :param top_n: 상위 N개 종목
    :return: {'종목명': '티커'} 딕셔너리
    """
    try:
        import FinanceDataReader as fdr

        # 전체 종목 리스트 (시가총액·거래량 정보 포함)
        df = fdr.StockListing(market)

        # 컬럼명이 버전마다 달라서 안전하게 처리
        # 'Volume' 또는 'Amount'(거래대금) 컬럼 활용
        candidates = ['Amount', 'Volume', 'Marcap']
        sort_col = None
        for c in candidates:
            if c in df.columns:
                sort_col = c
                break

        if sort_col is None:
            # 컬럼 못 찾으면 시가총액 기준
            sort_col = df.select_dtypes(include='number').columns[0]

        # 정렬 후 상위 N개 추출
        df_top = df.nlargest(top_n, sort_col)

        # 티커 컬럼 찾기 ('Code' 또는 'Symbol')
        code_col = 'Code' if 'Code' in df.columns else 'Symbol'
        name_col = 'Name'

        suffix = '.KS' if market == 'KOSPI' else '.KQ'
        result = {}
        for _, row in df_top.iterrows():
            code = str(row[code_col]).zfill(6)
            name = row[name_col]
            result[name] = f"{code}{suffix}"
        return result

    except Exception as e:
        print(f"⚠️ 거래대금 상위 추출 실패: {e}")
        print("   → 기본 종목 리스트를 사용합니다.")
        return {}


# ------------------------------------------------------------
# 2. 사용자 관심종목 관리 (저장/로드/추가/삭제)
# ------------------------------------------------------------
def load_watchlist() -> dict:
    """관심종목 파일 로드"""
    if not os.path.exists(WATCHLIST_FILE):
        return {}
    try:
        with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_watchlist(watchlist: dict):
    """관심종목 파일 저장"""
    with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=2)


def add_to_watchlist(name: str, ticker: str) -> dict:
    """관심종목 추가"""
    wl = load_watchlist()
    # .KS / .KQ 자동 처리
    ticker = normalize_ticker(ticker)
    wl[name] = ticker
    save_watchlist(wl)
    return wl


def remove_from_watchlist(name: str) -> dict:
    """관심종목 삭제"""
    wl = load_watchlist()
    if name in wl:
        del wl[name]
        save_watchlist(wl)
    return wl


# ------------------------------------------------------------
# 3. 티커 정규화 (한국 주식)
# ------------------------------------------------------------
def normalize_ticker(ticker: str) -> str:
    """
    사용자 입력 티커를 yfinance 형식으로 변환
    - '005930'         → '005930.KS'
    - '005930.KS'      → '005930.KS' (그대로)
    - '086520'         → '086520.KQ' (KOSDAQ 자동 판별 어려우므로 .KS 우선)

    KOSPI/KOSDAQ 구분이 필요하면 사용자가 직접 .KS / .KQ 입력
    """
    ticker = ticker.strip().upper()
    if '.' in ticker:
        return ticker
    # 6자리 숫자만 입력된 경우 .KS 우선 적용
    if ticker.isdigit() and len(ticker) == 6:
        return f"{ticker}.KS"
    return ticker


def search_stock_by_name(keyword: str) -> list:
    """
    종목명으로 검색해서 티커 찾기 (FinanceDataReader 활용)
    :return: [(종목명, 티커, 시장), ...]
    """
    try:
        import FinanceDataReader as fdr
        results = []
        for market in ['KOSPI', 'KOSDAQ']:
            df = fdr.StockListing(market)
            code_col = 'Code' if 'Code' in df.columns else 'Symbol'
            mask = df['Name'].str.contains(keyword, na=False)
            matched = df[mask].head(10)
            suffix = '.KS' if market == 'KOSPI' else '.KQ'
            for _, row in matched.iterrows():
                code = str(row[code_col]).zfill(6)
                results.append((row['Name'], f"{code}{suffix}", market))
        return results
    except Exception as e:
        return []
