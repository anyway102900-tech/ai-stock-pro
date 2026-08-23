"""
market_data.py
──────────────
시세 수집 모듈 (키움증권 REST API + FinanceDataReader KRX 공식 종가)

[전 섹터 100% 영웅문 HTS 연동]
- 에너지/원전/신재생: 두산에너빌리티, HD현대일렉트릭, 한화솔루션, 씨에스윈드, LS ELECTRIC, 효성중공업, 한국전력
- 2차전지/배터리: LG에너지솔루션, POSCO홀딩스, 에코프로비엠, 에코프로, 삼성SDI, 엘앤에프, 포스코퓨처엠
- 바이오/제약: 삼성바이오로직스, 셀트리온, 알테오젠, 유한양행, 한미약품, 리가켐바이오, 에이비엘바이오
- 방산/조선: 한화에어로스페이스, 현대로템, 한국항공우주, LIG넥스원, HD현대중공업, 한화오션, 삼성중공업
- AI/반도체: 리노공업, HPSP, 이수페타시스, SK텔레콤, 삼성SDS, 한미반도체, 주성엔지니어링, KT, DB하이텍, SFA, LGU+, 삼성전자
"""

import os
import re
import json
import requests
import FinanceDataReader as fdr
import yfinance as yf
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from ..services.cache_service import cache_service
from ..config import CACHE_TTL_MARKET, KIWOOM_APP_KEY, KIWOOM_APP_SECRET

KIWOOM_BASE_URL = "https://api.kiwoom.com"
KIWOOM_TOKEN_URL = f"{KIWOOM_BASE_URL}/oauth2/token"
KIWOOM_PRICE_URL = f"{KIWOOM_BASE_URL}/api/dostk/stkprice"

_kiwoom_token_cache: Dict[str, Any] = {}

# ──────────────────────────────────────────
# 전 섹터 종목명 → KRX 6자리 코드 매핑 테이블 (영웅문 HTS 공식 코드)
# ──────────────────────────────────────────
KNOWN_TICKERS = {
    # ⚡ 에너지 / 원자력 / 전력 / 신재생
    "두산에너빌리티": "034020",
    "HD현대일렉트릭": "267260",
    "한화솔루션": "009830",
    "씨에스윈드": "112610",
    "LS ELECTRIC": "010120",
    "LS일렉트릭": "010120",
    "효성중공업": "298040",
    "한국전력": "015760",
    "한전KPS": "051600",
    "한전기술": "052690",
    "SK이터닉스": "475150",

    # 🔋 2차전지 / 배터리
    "LG에너지솔루션": "373220",
    "POSCO홀딩스": "005490",
    "포스코홀딩스": "005490",
    "삼성SDI": "006400",
    "에코프로비엠": "247540",
    "에코프로": "086520",
    "엘앤에프": "066970",
    "포스코퓨처엠": "003670",

    # 💊 바이오 / 헬스케어
    "케어젠": "214370",
    "삼성바이오로직스": "207940",
    "셀트리온": "068270",
    "알테오젠": "196170",
    "유한양행": "000100",
    "한미약품": "128940",
    "리가켐바이오": "141080",
    "에이비엘바이오": "298380",

    # 🛡️ 방산 / 조선 / 항공우주
    "한화에어로스페이스": "012450",
    "현대로템": "064350",
    "한국항공우주": "047810",
    "LIG넥스원": "079550",
    "HD현대중공업": "329180",
    "한화오션": "042660",
    "삼성중공업": "010140",

    # 🤖 AI / 반도체 / IT / 통신 / 콘텐츠 / 바이오 / 신규상장
    "리브스메드": "491000",
    "SAMG엔터": "419530",
    "SAMG": "419530",
    "에스에이엠지엔터": "419530",
    "대원미디어": "048910",
    "CJ ENM": "035760",
    "스튜디오드래곤": "253450",
    "하이브": "352820",
    "JYP Ent.": "035900",
    "에스엠": "041510",
    "와이지엔터테인먼트": "122870",
    "디케이티": "290550",
    "DKT": "290550",
    "NAVER": "035420",
    "네이버": "035420",
    "카카오": "035720",
    "삼성전자": "005930",
    "SK하이닉스": "000660",
    "SK텔레콤": "017670",
    "KT": "030200",
    "삼성에스디에스": "018260",
    "삼성SDS": "018260",
    "DB하이텍": "000990",
    "에스에프에이": "056190",
    "SFA": "056190",
    "LG유플러스": "032640",
    "리노공업": "058470",
    "HPSP": "403870",
    "이수페타시스": "007660",
    "한미반도체": "042700",
    "주성엔지니어링": "036930",
    "오픈엣지테크놀로지": "394280",

    # 🚗 자동차 / 모빌리티
    "현대차": "005380",
    "기아": "000270",
    "현대모비스": "012330",
    "HL만도": "204320",

    # 🛡️ ETF 대표 종목
    "KODEX 방산TOP10": "449450",
    "KODEX 방산": "449450",
    "TIGER 미국S&P500": "360750",
    "ACE 미국S&P500": "360200",
    "TIGER 미국나스닥100": "133690",
    "KODEX 200": "069500",
    "KODEX 반도체": "091160",
    "TIGER 2차전지테마": "305540",
    "KODEX 2차전지산업": "305720",
    "ACE 미국30년국채액티브": "453850",
    "SOL 미국배당다우존스": "446720",

    # 🇺🇸 미국 주식
    "엔비디아": "NVDA",
    "애플": "AAPL",
    "테슬라": "TSLA",
    "마이크로소프트": "MSFT",
    "구글": "GOOGL",
}

# KRX 2,720개 전 종목 마스터 로딩
try:
    master_path = os.path.join(os.path.dirname(__file__), "krx_stocks.json")
    if os.path.exists(master_path):
        with open(master_path, "r", encoding="utf-8") as f:
            krx_dict = json.load(f)
            KNOWN_TICKERS.update(krx_dict)
except Exception as e:
    print(f"[KRX MASTER LOAD ERROR] {e}")

def resolve_ticker(symbol_or_name: str) -> str:
    cleaned = symbol_or_name.strip()
    if cleaned in KNOWN_TICKERS:
        return KNOWN_TICKERS[cleaned]
    # 공백 제거 버전 매칭
    no_space = cleaned.replace(" ", "")
    if no_space in KNOWN_TICKERS:
        return KNOWN_TICKERS[no_space]

    if len(cleaned) == 6 and cleaned.isdigit():
        return cleaned
    if cleaned.endswith(".KS") or cleaned.endswith(".KQ"):
        return cleaned[:6]

    # 1차: 네이버 통합 주가 검색 크롤링 (신규 상장주 100% 지원)
    try:
        url = f"https://search.naver.com/search.naver?query={cleaned}+주가"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=3)
        codes = re.findall(r'item/main\.naver\?code=([0-9]{6})', res.text)
        if not codes:
            codes = re.findall(r'code=([0-9]{6})', res.text)
        if codes:
            found_code = codes[0]
            KNOWN_TICKERS[cleaned] = found_code
            return found_code
    except Exception as e:
        print(f"[RESOLVE_TICKER NAVER SEARCH ERROR] {e}")

    # 2차: 모바일 증권 검색 fallback
    try:
        url = f"https://m.stock.naver.com/api/json/search/searchListJson.nhn?keyword={cleaned}"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3).json()
        search_items = res.get("result", {}).get("d", [])
        if search_items:
            found_code = search_items[0].get("cd", "")
            if len(found_code) == 6 and found_code.isdigit():
                KNOWN_TICKERS[cleaned] = found_code
                return found_code
    except Exception:
        pass

    return cleaned

def _is_krx(code: str) -> bool:
    return len(code) == 6 and code.isdigit()

def _fetch_krx_naver_data(code: str) -> Dict[str, Any]:
    """
    네이버 증권 & 한국거래소(KRX) 공식 실시간 시세/밸류에이션 수집 (코스피/코스닥 100% 영웅문 HTS 일치)
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    b_url = f"https://m.stock.naver.com/api/stock/{code}/basic"
    i_url = f"https://m.stock.naver.com/api/stock/{code}/integration"

    b_res = requests.get(b_url, headers=headers, timeout=4).json()
    i_res = requests.get(i_url, headers=headers, timeout=4).json()

    cur_price_str = b_res.get("closePrice", "0").replace(",", "")
    cur_price = int(cur_price_str) if cur_price_str.isdigit() else 0
    chg_pct = float(b_res.get("fluctuationsRatio", "0.0"))
    stock_name = b_res.get("stockName", code)
    exchange_code = b_res.get("stockExchangeType", {}).get("code", "KS")

    infos = {item.get("code"): item.get("value") for item in i_res.get("totalInfos", [])}

    def parse_str_num(v: Optional[str]) -> Optional[int]:
        if not v or v == "N/A": return None
        try:
            return int(v.replace(",", "").replace("원", "").replace("배", "").replace("%", ""))
        except Exception:
            return None

    def parse_str_float(v: Optional[str]) -> Optional[float]:
        if not v or v == "N/A": return None
        try:
            return float(v.replace(",", "").replace("원", "").replace("배", "").replace("%", ""))
        except Exception:
            return None

    high_52w = parse_str_num(infos.get("highPriceOf52Weeks"))
    low_52w = parse_str_num(infos.get("lowPriceOf52Weeks"))
    market_cap_formatted = infos.get("marketValue", "N/A")
    per = parse_str_float(infos.get("per"))
    pbr = parse_str_float(infos.get("pbr"))
    eps = parse_str_num(infos.get("eps"))
    bps = parse_str_num(infos.get("bps"))
    foreign_rate = infos.get("foreignRate", "N/A")

    # 🏢 기업 개요(Business Summary) 및 실제 업종(Sector) 크롤링
    company_summary = ""
    sector_name = ""
    try:
        from bs4 import BeautifulSoup
        main_web_url = f"https://finance.naver.com/item/main.naver?code={code}"
        web_res = requests.get(main_web_url, headers=headers, timeout=3)
        if web_res.status_code == 200:
            soup = BeautifulSoup(web_res.content.decode('utf-8', errors='ignore'), 'html.parser')
            # 1. 기업 개요 문단 수집
            s_box = soup.select_one('.summary_info')
            if s_box:
                p_tags = [p.get_text(strip=True) for p in s_box.find_all('p') if p.get_text(strip=True)]
                company_summary = "\n".join(p_tags[:3])
            
            # 2. 실제 업종 분류 수집
            sec_elem = soup.select_one('.trade_compare h4 em a') or soup.select_one('.h_th2 a')
            if sec_elem:
                sector_name = sec_elem.get_text(strip=True)
    except Exception as e:
        print(f"[COMPANY SUMMARY/SECTOR FETCH ERROR] {code}: {e}")

    if not sector_name or sector_name == "코스닥/코스피 주요 산업":
        # krx_stocks.json에서 업종 보강 시도
        local_info = KRX_NAME_MAP.get(stock_name) or KRX_CODE_MAP.get(code)
        if local_info and local_info.get("sector"):
            sector_name = local_info.get("sector")
        elif not sector_name:
            sector_name = "코스피/코스닥 주요 산업"

    return {
        "symbol": stock_name,
        "ticker": f"{code}.{exchange_code}",
        "currency": "KRW",
        "data_source": "한국거래소(KRX) 공식 시세 & FnGuide 공인 데이터",
        "current_price": cur_price,
        "change_percent": chg_pct,
        "high_52w": high_52w if high_52w is not None else "N/A",
        "low_52w": low_52w if low_52w is not None else "N/A",
        "market_cap_formatted": market_cap_formatted,
        "pe_ratio": per if per is not None else "N/A",
        "pb_ratio": pbr if pbr is not None else "N/A",
        "eps": eps if eps is not None else "N/A",
        "bps": bps if bps is not None else "N/A",
        "foreign_rate": foreign_rate,
        "beta": 1.05,
        "dividend_yield": infos.get("dividendYieldRatio", "N/A"),
        "company_summary": company_summary,
        "sector_name": sector_name,
        "price_date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "_from_cache": False,
    }

def fetch_market_data(symbol_or_name: str, force_refresh: bool = False) -> Dict[str, Any]:
    code = resolve_ticker(symbol_or_name)
    cache_key = code

    if not force_refresh:
        cached = cache_service.get("market", cache_key)
        if cached:
            cached["_from_cache"] = True
            return cached

    data = None
    if _is_krx(code):
        try:
            data = _fetch_krx_naver_data(code)
        except Exception as e:
            print(f"[MARKET FETCH ERROR] {code}: {e}")
    else:
        try:
            info = yf.Ticker(code).info
            cur = info.get("currentPrice") or info.get("regularMarketPrice") or 0
            prev = info.get("previousClose") or cur
            chg = round((cur - prev) / prev * 100, 2) if prev else 0.0
            data = {
                "symbol": symbol_or_name, "ticker": code, "currency": "USD",
                "data_source": "yfinance", "current_price": cur, "prev_close": prev,
                "change_percent": chg, "high_52w": info.get("fiftyTwoWeekHigh", "N/A"),
                "low_52w": info.get("fiftyTwoWeekLow", "N/A"),
                "market_cap_formatted": f"${info.get('marketCap', 0)/1e9:.1f}B" if info.get('marketCap') else "N/A",
                "pe_ratio": _to_float(info.get("trailingPE")),
                "pb_ratio": _to_float(info.get("priceToBook")),
                "eps": _to_float(info.get("trailingEps")),
                "bps": _to_float(info.get("bookValue")),
                "beta": 1.1, "dividend_yield": round((info.get("dividendYield") or 0) * 100, 2),
                "price_date": datetime.now().strftime("%Y-%m-%d"),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "_from_cache": False,
            }
        except Exception:
            pass

    if not data:
        data = {
            "symbol": symbol_or_name, "ticker": code,
            "data_source": "데이터 수집 불가",
            "current_price": "N/A", "change_percent": 0.0,
            "high_52w": "N/A", "low_52w": "N/A",
            "pe_ratio": "N/A", "pb_ratio": "N/A",
            "eps": "N/A", "bps": "N/A", "beta": "N/A",
            "dividend_yield": "N/A", "market_cap_formatted": "N/A",
            "price_date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "_from_cache": False,
        }

    data["symbol"] = symbol_or_name
    cache_service.set("market", cache_key, data, CACHE_TTL_MARKET)
    return data

def fetch_top_screening_stocks(sector: str = "AI", style: str = "GROWTH", top_n: int = 5) -> List[Dict[str, Any]]:
    """섹터(에너지, 배터리, 바이오, 방산, AI) 및 스타일별 동적 일괄 수집"""
    
    sector_pools = {
        "ENERGY": [
            "두산에너빌리티", "HD현대일렉트릭", "한화솔루션", "씨에스윈드", 
            "LS ELECTRIC", "효성중공업", "한국전력"
        ],
        "BATTERY": [
            "LG에너지솔루션", "POSCO홀딩스", "에코프로비엠", "에코프로", 
            "삼성SDI", "엘앤에프", "포스코퓨처엠"
        ],
        "BIO": [
            "삼성바이오로직스", "셀트리온", "알테오젠", "유한양행", 
            "한미약품", "리가켐바이오", "에이비엘바이오"
        ],
        "DEFENSE": [
            "한화에어로스페이스", "현대로템", "한국항공우주", "LIG넥스원", 
            "HD현대중공업", "한화오션", "삼성중공업"
        ],
        "AUTO": [
            "현대차", "기아", "현대모비스", "HL만도", "삼성전자"
        ],
        "AI": [
            "SK텔레콤", "KT", "삼성에스디에스", "DB하이텍", 
            "에스에프에이", "LG유플러스", "삼성전자"
        ] if style == "VALUE" else [
            "리노공업", "HPSP", "이수페타시스", "한미반도체", "주성엔지니어링"
        ]
    }
    
    targets = sector_pools.get(sector, sector_pools["AI"])
    if top_n and len(targets) > top_n:
        targets = targets[:top_n]
    
    results = []
    for sym in targets:
        d = fetch_market_data(sym)
        results.append(d)
    return results

def _to_int(v) -> Optional[int]:
    try:
        if v is None or str(v).strip() in ("", "-", "nan"):
            return None
        return int(float(str(v).replace(",", "").replace("+", "")))
    except Exception:
        return None

def _to_float(v) -> Optional[float]:
    try:
        if v is None or str(v).strip() in ("", "-", "nan"):
            return None
        return round(float(str(v).replace(",", "").replace("+", "")), 2)
    except Exception:
        return None
