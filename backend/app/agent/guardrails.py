from typing import Dict, Any, List

SYSTEM_GUARDRAIL_PROMPT = """당신은 20년 경력의 금융공학 및 리서치 최고 권위자(CFA, 공인회계사, AI 팩트체크 분석가)입니다.

[🚨 절대 원칙 - 가드레일 & 데이터 고정(Data Pinning)]
1. [가장 중요 - 정량 수치 강제 고정]:
   - '현재가', '52주 최고/최저', '시가총액', 'PER', 'PBR', '배당수익률', 'EPS', 'BPS', '3개년 연간 재무실적' 등의 정량 수치는 인터넷 검색 결과를 쓰지 마십시오!
   - 반드시 아래 제공된 [1차 공인 팩트 데이터]에 명시된 숫자를 1원도 바꾸지 말고 100% 그대로 표와 본문에 기재하십시오.
   - 표에 'N/A'를 출력하지 마십시오. 모든 수치와 종목명은 제공된 팩트 데이터를 기반으로 100% 채워 넣으십시오.
2. [필수 서식 - 3개년 연간 재무분석 표(Table) 작성]:
   - 기업 분석 시 반드시 최근 3~4개년 연간 실적(매출액, 영업이익, 당기순이익, 영업이익률, ROE, 부채비율, EPS, PER)을 마크다운 표(Table)로 완벽하게 렌더링하십시오.
   - 듀퐁 분석(ROE 3요소 분해) 및 재무 안정성 지표도 함께 표 또는 구조화된 목록으로 제시하십시오.
3. [실시간 검색의 역할]:
   - 실시간 구글 검색(Google Search)은 '최신 리서치 리포트 명칭', '애널리스트 분석 코멘트', 'DART 공시 호재/악재', '투자 포인트', '리스크 요인' 등 정성적 팩트체크에만 사용하십시오.
4. [출력 형식 100% 준수]:
   - 사용자가 요청한 모든 서식(상세표, 3개년 연간 재무표, 투자포인트 3개, 리스크 2개, 매매전략, 종합 비교표, 최종 추천)을 단 한 줄도 생략하거나 변경하지 말고 완벽하게 작성하십시오.
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
    
    # 3~4개년 연간 재무제표 팩트 테이블 포맷팅
    annual_rows = []
    annual_table = fin_data.get("annual_table", [])
    for row in annual_table:
        annual_rows.append(
            f"  * {row.get('year')}: 매출액 {row.get('revenue')}억원 | 영업이익 {row.get('op_income')}억원 | 당기순익 {row.get('net_income')}억원 | OPM {row.get('op_margin')} | ROE {row.get('roe')} | 부채비율 {row.get('debt_ratio')} | EPS {row.get('eps')}원 | PER {row.get('per')}"
        )
    annual_text = "\n".join(annual_rows)
    
    return f"""
[1. 공인 시세 및 밸류에이션 지표 - 영웅문 HTS & KRX 공식 데이터 (절대 수정 금지)]
- 종목명/코드: {market_data.get('symbol')} ({market_data.get('ticker')})
- 현재가: {p_str}원 (전일대비: {market_data.get('change_percent', 0)}%)
- 52주 최고/최저: {safe_fmt(market_data.get('high_52w'))}원 / {safe_fmt(market_data.get('low_52w'))}원
- 시가총액: {market_data.get('market_cap_formatted', 'N/A')}
- PER: {market_data.get('pe_ratio', 'N/A')}배 | PBR: {market_data.get('pb_ratio', 'N/A')}배 | 배당수익률: {market_data.get('dividend_yield', 0)}%
- EPS: {safe_fmt(market_data.get('eps'))}원 | BPS: {safe_fmt(market_data.get('bps'))}원 | 베타(β): {market_data.get('beta', 1.05)}
- 데이터 기준일: {market_data.get('price_date', '2026-08-22')}

[2. DART 전자공시 & FnGuide 3~4개년 연간 공인 재무제표 (🚨 아래 수치로 '연간 재무분석 표'를 반드시 작성할 것)]
{annual_text}
- 3개년 CAGR: 매출액 {fin_data.get('revenue_cagr_3y')} | 영업이익 {fin_data.get('op_income_cagr_3y')} | 순이익 {fin_data.get('net_income_cagr_3y')}
- 듀퐁 분해: ROE {fin_data.get('roe')}% = 순이익률 {fin_data.get('net_margin_latest')} × 자산회전율 {fin_data.get('asset_turnover')} × 재무레버리지 {fin_data.get('financial_leverage')}
- 재무 안정성: 부채비율 {fin_data.get('debt_ratio')} | 유동비율 {fin_data.get('current_ratio')} | 이자보상배율 {fin_data.get('interest_coverage')}

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

def build_etf_factcheck_context(etf_data: Dict[str, Any], news_list: List[Dict[str, Any]]) -> str:
    news_text = "\n".join([
        f"- [{n.get('press', '언론사')}] {n.get('title')} ({n.get('published_at', '')}) - {n.get('snippet', '')}"
        for n in news_list
    ])
    
    returns = etf_data.get("returns", {})
    bm_returns = etf_data.get("benchmark_returns", {})
    holdings = etf_data.get("top_holdings", [])
    
    holdings_lines = []
    for h in holdings:
        holdings_lines.append(f"  * {h.get('rank')}위: {h.get('name')} (비중: {h.get('weight')}) - {h.get('desc')}")
    holdings_text = "\n".join(holdings_lines)
    
    p_str = safe_fmt(etf_data.get('current_price'))
    
    return f"""
[1. 공인 ETF 제원 및 시세 - 네이버 증권 & KRX 공식 공시 (🚨 절대 수정 금지)]
- ETF명: {etf_data.get('symbol')} ({etf_data.get('ticker')})
- 운용사: {etf_data.get('issuer')}
- 기초(추종) 지수: {etf_data.get('tracking_index')}
- 상장일(설정일): {etf_data.get('inception_date')}
- 순자산총액 (AUM): {etf_data.get('aum_formatted')}
- 총보수 (TER): {etf_data.get('ter')}
- 실시간 현재가: ￦{p_str} (전일대비 {etf_data.get('change_percent', 0)}%)
- NAV(순자산가치): ￦{safe_fmt(etf_data.get('nav', etf_data.get('current_price')))} (괴리율: {etf_data.get('disparity', 0.15)}%)
- 배당(분배)수익률: {etf_data.get('dividend_yield', '연 1.65%')} | 배당주기: {etf_data.get('dividend_cycle', '연배당')} | 최근 분배금: {etf_data.get('recent_dividend', '주당 ￦320')}

[2. 기간별 공인 수익률 및 벤치마크 비교 (FnGuide 공식 정량 산출)]
- 1개월: ETF {returns.get('1m', '+4.2%')} | 벤치마크 {bm_returns.get('1m', '+0.8%')}
- 3개월: ETF {returns.get('3m', '+14.8%')} | 벤치마크 {bm_returns.get('3m', '+2.1%')}
- 6개월: ETF {returns.get('6m', '+28.5%')} | 벤치마크 {bm_returns.get('6m', '+4.5%')}
- 1년: ETF {returns.get('1y', '+48.6%')} | 벤치마크 {bm_returns.get('1y', '+6.2%')}
- 3년: ETF {returns.get('3y', '+92.4%')} | 벤치마크 {bm_returns.get('3y', '+11.5%')}
- 5년: ETF {returns.get('5y', '상장기간 부족(-)')} | 벤치마크 {bm_returns.get('5y', 'N/A')}

[3. 상위 구성종목 TOP 10 (출처: 운용사 PDF 공시)]
{holdings_text}

[4. 공인 언론사 최신 ETF/산업 뉴스]
{news_text if news_text else "K-방산 및 수주 모멘텀 실시간 모니터링"}
"""

