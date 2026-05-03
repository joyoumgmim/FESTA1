"""
=============================================================
  FESTA - 포트폴리오 관리 모듈
=============================================================
  실제 매수 내역을 저장/로드/관리
  - 종목별 매수가, 수량, 매수일, 매수 이유 (3줄 기록)
=============================================================
"""

import json
import os
from datetime import datetime

PORTFOLIO_FILE = "portfolio.json"


def load_portfolio() -> list:
    """포트폴리오 파일 로드"""
    if not os.path.exists(PORTFOLIO_FILE):
        return []
    try:
        with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def save_portfolio(portfolio: list):
    """포트폴리오 파일 저장"""
    with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
        json.dump(portfolio, f, ensure_ascii=False, indent=2)


def add_position(name: str, ticker: str, buy_price: float, quantity: int,
                 buy_date: str = None, reason: str = "",
                 exit_condition: str = "", max_loss: str = "") -> list:
    """포지션 추가 (테스타 3줄 기록 포함)"""
    portfolio = load_portfolio()
    if buy_date is None:
        buy_date = datetime.now().strftime('%Y-%m-%d')

    position = {
        'id': f"{ticker}_{buy_date}_{datetime.now().strftime('%H%M%S')}",
        '종목명': name,
        '티커': ticker,
        '매수가': buy_price,
        '수량': quantity,
        '매수일': buy_date,
        '사는이유': reason,            # 테스타 3줄 기록 ①
        '팔자리': exit_condition,       # 테스타 3줄 기록 ②
        '최대손실제한': max_loss,        # 테스타 3줄 기록 ③
    }
    portfolio.append(position)
    save_portfolio(portfolio)
    return portfolio


def remove_position(position_id: str) -> list:
    """포지션 삭제 (매도 처리)"""
    portfolio = load_portfolio()
    portfolio = [p for p in portfolio if p.get('id') != position_id]
    save_portfolio(portfolio)
    return portfolio


def get_position_by_id(position_id: str) -> dict:
    """ID로 포지션 조회"""
    portfolio = load_portfolio()
    for p in portfolio:
        if p.get('id') == position_id:
            return p
    return None
