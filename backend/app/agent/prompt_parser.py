import re
from typing import Dict, Any, List

STOPWORDS = {
    "의", "에", "를", "을", "은", "는", "이", "가", "과", "와", "로", "으로",
    "오늘", "오늘의", "단타", "뉴스", "시장", "조건", "5개", "7개", "전체", "모닝브리핑",
    "브리핑", "추천", "발굴", "전망", "분석", "종목", "기업", "대상", "테마", "주식", "섹터"
}

def parse_rice_prompt(prompt_text: str) -> Dict[str, Any]:
    """
    RICE 프롬프트에서 메뉴 유형, 섹터, 스타일, 종목수(Top N), 대상 종목, 투자금을 정밀 파싱합니다.
    """
    # 1. 메뉴 유형 감지
    menu_type = "GENERAL"
    style = "GROWTH"  # 기본 성장주
    top_n = 5
    
    if "7개" in prompt_text or "TOP 7" in prompt_text or "TOP7" in prompt_text:
        top_n = 7
    elif "5개" in prompt_text or "TOP 5" in prompt_text or "TOP5" in prompt_text:
        top_n = 5

    if any(k in prompt_text for k in ["가치주 발굴", "가치주", "저PBR", "배당수익률", "상대가치 저평가"]):
        style = "VALUE"
        
    if any(k in prompt_text for k in ["종목발굴", "TOP 5", "TOP 7", "발굴", "성장주 발굴", "가치주 발굴", "스크리닝"]):
        menu_type = "DISCOVERY" # 1. 종목발굴
    elif any(k in prompt_text for k in ["듀퐁", "DuPont", "재무 분석", "재무 건전성"]):
        menu_type = "FINANCIAL" # 2. 재무 종합분석
    elif any(k in prompt_text for k in ["상대가치", "적정 주가", "적정가", "안전마진", "가중평균 적정가", "밸류에이션"]):
        menu_type = "VALUATION" # 3. 밸류에이션
    elif any(k in prompt_text for k in ["경제적 해자", "Moat", "브랜드 파워", "전환비용", "네트워크 효과"]):
        menu_type = "MOAT" # 4. 경제적 해자
    elif any(k in prompt_text for k in ["시나리오", "CRO", "베타", "Bull", "Bear", "손익 관리", "스트레스 테스트"]):
        menu_type = "RISK" # 5. 리스크 & 시나리오
    elif any(k in prompt_text for k in ["모닝브리핑", "단타", "단기 트레이딩", "수혜 종목", "새벽 공시"]):
        menu_type = "MORNING" # 6. 단타 모닝브리핑
    elif any(k in prompt_text for k in ["포트폴리오 구성", "1000만원", "자산배분", "분할 매수", "리밸런싱"]):
        menu_type = "PORTFOLIO" # 7. 포트폴리오 구성
    elif any(k in prompt_text for k in ["ETF", "총보수", "TER", "추종 지수", "추적오차"]):
        menu_type = "ETF" # 8. ETF 분석

    # 2. 섹터(Sector) 동적 감지
    sector = "AI"
    if any(k in prompt_text for k in ["에너지", "원자력", "원전", "태양광", "풍력", "수소", "전력망", "전력", "신재생"]):
        sector = "ENERGY"
    elif any(k in prompt_text for k in ["2차전지", "배터리", "양극재", "음극재", "리튬"]):
        sector = "BATTERY"
    elif any(k in prompt_text for k in ["바이오", "제약", "헬스케어", "신약"]):
        sector = "BIO"
    elif any(k in prompt_text for k in ["방산", "조선", "방위산업", "우주항공", "항공우주"]):
        sector = "DEFENSE"
    elif any(k in prompt_text for k in ["자동차", "모빌리티", "자율주행", "완성차"]):
        sector = "AUTO"
    elif any(k in prompt_text for k in ["플랫폼", "인터넷", "게임", "엔터", "콘텐츠"]):
        sector = "PLATFORM"
    else:
        sector = "AI"

    # 3. 분석 대상 단일/대표 종목 추출
    symbol = None
    # '분석 대상:', '분석 대상 :', '종목명:' 등의 다양한 패턴 매칭
    symbol_match = re.search(r'(?:분석\s*대상|종목명|대상\s*종목|기업명|구성\s*종목)[:\s]*([가-힣A-Za-z0-9\s,]+)', prompt_text)
    if symbol_match:
        cand_line = symbol_match.group(1).split('\n')[0].strip()
        # 콤마로 나뉘어 있으면 첫 번째 대표 종목 선택
        first_cand = cand_line.split(',')[0].strip()
        if first_cand and first_cand not in STOPWORDS and len(first_cand) > 1:
            symbol = first_cand

    if not symbol:
        # ETF 전용 패턴 우선 검사
        etf_match = re.search(r'(?:KODEX|TIGER|ACE|SOL|PLUS|ARIRANG|KBSTAR|RISE|HANARO|TIMEFOLIO|KOSEF)\s*[가-힣A-Za-z0-9\-_+]+', prompt_text)
        if etf_match:
            symbol = etf_match.group(0).strip()
            menu_type = "ETF"

    if not symbol:
        known_candidates = [
            "KODEX 방산TOP10", "TIGER 미국S&P500", "ACE 미국S&P500", "TIGER 미국나스닥100",
            "KODEX 반도체", "TIGER 2차전지테마", "KODEX 200", "ACE 미국30년국채액티브",
            "NAVER", "네이버", "카카오", "두산에너빌리티", "HD현대일렉트릭", "한화솔루션", "씨에스윈드", 
            "LS ELECTRIC", "효성중공업", "한국전력", "LG에너지솔루션", "포스코홀딩스", "POSCO홀딩스", "에코프로비엠", 
            "에코프로", "삼성SDI", "삼성바이오로직스", "셀트리온", "알테오젠", "유한양행", "한화에어로스페이스", "현대로템", 
            "한국항공우주", "리노공업", "한미반도체", "삼성전자", "SK하이닉스", "SK텔레콤", "KT", 
            "삼성에스디에스", "삼성SDS", "DB하이텍", "에스에프에이", "LG유플러스", "현대차", "기아"
        ]
        for cand in known_candidates:
            if cand in prompt_text:
                symbol = cand
                if any(etf_p in cand for etf_p in ["KODEX", "TIGER", "ACE", "SOL", "PLUS", "ARIRANG"]):
                    menu_type = "ETF"
                break

    # 기본 대표 종목 할당
    if not symbol:
        if sector == "ENERGY":
            symbol = "두산에너빌리티"
        elif sector == "BATTERY":
            symbol = "LG에너지솔루션"
        elif sector == "BIO":
            symbol = "삼성바이오로직스"
        elif sector == "DEFENSE":
            symbol = "한화에어로스페이스"
        elif menu_type == "MORNING":
            symbol = "HD현대일렉트릭"
        elif menu_type == "DISCOVERY":
            symbol = "SK텔레콤" if style == "VALUE" else "리노공업"
        else:
            symbol = "NAVER"

    # 4. 투자금 추출
    budget = 10_000_000
    budget_match = re.search(r'(?:총 투자금|투자금)[:\s]*([0-9]+)만원', prompt_text)
    if budget_match:
        budget = int(budget_match.group(1)) * 10_000

    return {
        "menu_type": menu_type,
        "sector": sector,
        "style": style,
        "top_n": top_n,
        "symbol": symbol,
        "budget": budget,
        "raw_prompt": prompt_text
    }
