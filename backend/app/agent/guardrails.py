from typing import Dict, Any, List

SYSTEM_GUARDRAIL_PROMPT = """당신은 20년 경력의 금융공학 및 리서치 최고 권위자(CFA, 공인회계사, AI 팩트체크 분석가)입니다.

[🚨 절대 원칙 - 가드레일 & 데이터 고정(Data Pinning)]
1. [가장 중요 - 정량 수치 강제 고정]:
   - '현재가', '52주 최고/최저', '시가총액', 'PER', 'PBR', '배당수익률', 'EPS', 'BPS' 등의 정량 수치는 인터넷 검색 결과를 쓰지 마십시오!
   - 반드시 아래 제공된 [1차 공인 팩트 데이터]에 명시된 숫자를 1원도 바꾸지 말고 100% 그대로 표와 본문에 기재하십시오.
   - 표에 'N/A'를 출력하지 마십시오. 모든 수치와 종목명은 제공된 팩트 데이터를 기반으로 100% 채워 넣으십시오.
2. [실시간 검색의 역할]:
   - 실시간 구글 검색(Google Search)은 '최신 리서치 리포트 명칭', '애널리스트 분석 코멘트', 'DART 공시 호재/악재', '투자 포인트', '리스크 요인' 등 정성적 팩트체크에만 사용하십시오.
3. [출력 형식 100% 준수]:
   - 사용자가 프롬프트에서 요청한 [E (Example)]의 모든 서식(1순위~5순위 또는 1순위~7순위 상세표, 투자포인트 3개, 리스크 2개, 매매전략, 종합 비교표, 최종 추천)을 단 한 줄도 생략하거나 변경하지 말고 완벽하게 작성하십시오.
"""

def safe_fmt(val, default="N/A"):
    if val is None or val == "N/A":
        return default
    if isinstance(val, (int, float)):
        return f"{int(val):,}"
    return str(val)

def build_factcheck_context(market_data: Dict[str, Any], fin_data: Dict[str, Any], news_list: List[Dict[str, Any]]) -> str:
    news_text = "\n".join([
        f"- [{n.get('press', '언론사')}] {n.get('title')} ({n.get('published_at', '')}) - {n.get('snippet', '')}"
        for n in news_list
    ])
    
    p_str = safe_fmt(market_data.get('current_price'))
    
    return f"""
[1. 공인 시세 및 밸류에이션 지표 - 영웅문 HTS & KRX 공식 데이터 (절대 수정 금지)]
- 종목명/코드: {market_data.get('symbol')} ({market_data.get('ticker')})
- 현재가: {p_str}원 (전일대비: {market_data.get('change_percent', 0)}%)
- 52주 최고/최저: {safe_fmt(market_data.get('high_52w'))}원 / {safe_fmt(market_data.get('low_52w'))}원
- 시가총액: {market_data.get('market_cap_formatted', 'N/A')}
- PER: {market_data.get('pe_ratio', 'N/A')}배 | PBR: {market_data.get('pb_ratio', 'N/A')}배 | 배당수익률: {market_data.get('dividend_yield', 0)}%
- EPS: {safe_fmt(market_data.get('eps'))}원 | BPS: {safe_fmt(market_data.get('bps'))}원 | 베타(β): {market_data.get('beta', 1.05)}
- 데이터 기준일: {market_data.get('price_date', '2026-08-22')}

[2. DART 전자공시 재무제표 팩트 - 출처: 금융감독원 Open DART]
- ROE: {fin_data.get('roe')}% (듀퐁 분해: 순익률 {fin_data.get('net_margin_latest')} × 자산회전율 {fin_data.get('asset_turnover')} × 레버리지 {fin_data.get('financial_leverage')})
- 부채비율: {fin_data.get('debt_ratio')} | 유동비율: {fin_data.get('current_ratio')} | 이자보상배율: {fin_data.get('interest_coverage')}배
- 3개년 매출 CAGR: {fin_data.get('revenue_cagr_3y')} | 영업이익 CAGR: {fin_data.get('op_income_cagr_3y')}

[3. 공인 화이트리스트 언론사 최신 뉴스 속보]
{news_text if news_text else "최신 등록된 검증 기사 실시간 모니터링 중"}
"""

def build_multi_factcheck_context(stocks_data: List[Dict[str, Any]]) -> str:
    lines = [
        "[1차 공인 팩트 데이터: 영웅문 HTS & KRX 공식 시세 (🚨 아래 현재가/지표 숫자를 표에 100% 그대로 반영할 것)]"
    ]
    for i, s in enumerate(stocks_data, 1):
        p_str = safe_fmt(s.get('current_price'))
        h_str = safe_fmt(s.get('high_52w'))
        l_str = safe_fmt(s.get('low_52w'))
        lines.append(
            f"{i}순위: [{s.get('symbol')} ({s.get('ticker')})] "
            f"현재가={p_str}원 | 등락률={s.get('change_percent', 0)}% | 52주고저={h_str}원/{l_str}원 | "
            f"시가총액={s.get('market_cap_formatted', 'N/A')} | PER={s.get('pe_ratio', 'N/A')}배 | "
            f"PBR={s.get('pb_ratio', 'N/A')}배 | 배당수익률={s.get('dividend_yield', 0)}% | "
            f"EPS={safe_fmt(s.get('eps'))}원 | BPS={safe_fmt(s.get('bps'))}원"
        )
    return "\n".join(lines)
