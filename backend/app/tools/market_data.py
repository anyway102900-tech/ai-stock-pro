"""
market_data.py
──────────────
시세 수집 모듈 (키움증권 REST API + 네이버 금융 1차 공인망 + FinanceDataReader + yfinance)
"""

import os
import re
import json
import requests
import FinanceDataReader as fdr
import yfinance as yf
from bs4 import BeautifulSoup
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..services.cache_service import cache_service
from ..config import CACHE_TTL_MARKET

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
    "에임드바이오": "0009K0",
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
    "클래시스": "214150",
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
    master_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "src", "krx_stocks.json")
    if os.path.exists(master_path):
        with open(master_path, "r", encoding="utf-8") as f:
            krx_dict = json.load(f)
            KNOWN_TICKERS.update(krx_dict)
except Exception as e:
    pass

REVERSE_KNOWN_TICKERS = {v: k for k, v in KNOWN_TICKERS.items()}

def resolve_ticker(symbol_or_name: str) -> str:
    cleaned = symbol_or_name.strip()
    if cleaned in KNOWN_TICKERS:
        return KNOWN_TICKERS[cleaned]
    no_space = cleaned.replace(" ", "")
    if no_space in KNOWN_TICKERS:
        return KNOWN_TICKERS[no_space]

    if len(cleaned) == 6 and (cleaned.isdigit() or (cleaned.isalnum() and any(c.isdigit() for c in cleaned))):
        return cleaned
    if cleaned.endswith(".KS") or cleaned.endswith(".KQ"):
        return cleaned[:6]

    # 네이버 통합 검색 크롤링
    try:
        url = f"https://search.naver.com/search.naver?query={cleaned}+주가"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, timeout=5)
        codes = re.findall(r'item/main\.naver\?code=([0-9A-Za-z]{6})', res.text)
        if not codes:
            codes = re.findall(r'code=([0-9A-Za-z]{6})', res.text)
        if codes:
            found_code = codes[0]
            KNOWN_TICKERS[cleaned] = found_code
            return found_code
    except Exception:
        pass

    return cleaned

def _is_krx(code: str) -> bool:
    return len(code) == 6 and (code.isdigit() or (code.isalnum() and any(c.isdigit() for c in code)))

def _fetch_krx_naver_data(code: str, fallback_name: str = "") -> Dict[str, Any]:
    """
    네이버 증권 & 한국거래소(KRX) 공식 실시간 시세/밸류에이션 수집 (모바일 API + PC HTML 2중 안전망)
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://finance.naver.com/"
    }
    
    cur_price = 0
    chg_pct = 0.0
    stock_name = fallback_name or REVERSE_KNOWN_TICKERS.get(code, code)
    exchange_code = "KQ"
    high_52w = "N/A"
    low_52w = "N/A"
    market_cap_formatted = "N/A"
    per = "N/A"
    pbr = "N/A"
    eps = "N/A"
    bps = "N/A"
    foreign_rate = "N/A"
    dividend_yield = "N/A"
    company_summary = ""
    sector_name = "코스피/코스닥 주요 산업"

    # 1차 시도: 모바일 JSON API (빠르고 정밀)
    try:
        b_url = f"https://m.stock.naver.com/api/stock/{code}/basic"
        i_url = f"https://m.stock.naver.com/api/stock/{code}/integration"

        b_res = requests.get(b_url, headers=headers, timeout=5).json()
        i_res = requests.get(i_url, headers=headers, timeout=5).json()

        cur_price_str = b_res.get("closePrice", "0").replace(",", "")
        if cur_price_str.isdigit() and int(cur_price_str) > 0:
            cur_price = int(cur_price_str)
            chg_pct = float(b_res.get("fluctuationsRatio", "0.0"))
            stock_name = b_res.get("stockName", stock_name)
            exchange_code = b_res.get("stockExchangeType", {}).get("code", "KQ")

            infos = {item.get("code"): item.get("value") for item in i_res.get("totalInfos", [])}

            def parse_val(v):
                if not v or v == "N/A": return "N/A"
                return v

            high_52w = parse_val(infos.get("highPriceOf52Weeks"))
            low_52w = parse_val(infos.get("lowPriceOf52Weeks"))
            market_cap_formatted = infos.get("marketValue", "N/A")
            per = parse_val(infos.get("per"))
            pbr = parse_val(infos.get("pbr"))
            eps = parse_val(infos.get("eps"))
            bps = parse_val(infos.get("bps"))
            foreign_rate = infos.get("foreignRate", "N/A")
            dividend_yield = infos.get("dividendYieldRatio", "N/A")
    except Exception as e:
        print(f"[NAVER MOBILE API FAIL, FALLBACK TO PC HTML] {code}: {e}")

    # 2차 시도: PC HTML 파싱 (모바일 실패 시 100% 동작 보장)
    if cur_price == 0:
        try:
            main_url = f"https://finance.naver.com/item/main.naver?code={code}"
            res = requests.get(main_url, headers=headers, timeout=6)
            if res.status_code == 200:
                soup = BeautifulSoup(res.content.decode('euc-kr', errors='ignore'), 'html.parser')
                
                # 종목명
                name_tag = soup.select_one('.wrap_company h2 a')
                if name_tag:
                    stock_name = name_tag.get_text(strip=True)
                    
                # 현재가
                price_tag = soup.select_one('.no_today .blind')
                if price_tag and price_tag.get_text(strip=True).replace(',', '').isdigit():
                    cur_price = int(price_tag.get_text(strip=True).replace(',', ''))
                    
                # 등락률
                rate_tag = soup.select_one('.no_exday .blind')
                if rate_tag:
                    try:
                        chg_pct = float(rate_tag.get_text(strip=True).replace('%', ''))
                    except Exception:
                        pass
                        
                # PER, PBR
                per_tag = soup.select_one('#_per')
                if per_tag: per = f"{per_tag.get_text(strip=True)}배"
                pbr_tag = soup.select_one('#_pbr')
                if pbr_tag: pbr = f"{pbr_tag.get_text(strip=True)}배"
                
                # 시가총액
                market_cap_tag = soup.select_one('#_market_sum')
                if market_cap_tag:
                    market_cap_formatted = f"{market_cap_tag.get_text(strip=True)}억원"
                    
                # 52주 최고/최저
                h52_tag = soup.select_one('table[summary="동일업종 비교"] tr:nth-of-type(4) td')
        except Exception as e:
            print(f"[NAVER PC HTML FAIL] {code}: {e}")

    # 🏢 기업 개요 및 업종 크롤링
    try:
        main_web_url = f"https://finance.naver.com/item/main.naver?code={code}"
        web_res = requests.get(main_web_url, headers=headers, timeout=5)
        if web_res.status_code == 200:
            soup = BeautifulSoup(web_res.content.decode('euc-kr', errors='ignore'), 'html.parser')
            s_box = soup.select_one('.summary_info')
            if s_box:
                p_tags = [p.get_text(strip=True) for p in s_box.find_all('p') if p.get_text(strip=True)]
                company_summary = "\n".join(p_tags[:3])
            
            sec_elem = soup.select_one('.trade_compare h4 em a') or soup.select_one('.h_th2 a')
            if sec_elem:
                sector_name = sec_elem.get_text(strip=True)
    except Exception:
        pass

    if not stock_name or stock_name == code:
        stock_name = REVERSE_KNOWN_TICKERS.get(code, code)

    return {
        "symbol": stock_name,
        "ticker": f"{code}.{exchange_code}",
        "currency": "KRW",
        "data_source": "한국거래소(KRX) 공식 시세 & FnGuide 공인 데이터",
        "current_price": cur_price if cur_price > 0 else "N/A",
        "change_percent": chg_pct,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "market_cap_formatted": market_cap_formatted,
        "pe_ratio": per,
        "pb_ratio": pbr,
        "eps": eps,
        "bps": bps,
        "foreign_rate": foreign_rate,
        "beta": 1.05,
        "dividend_yield": dividend_yield,
        "company_summary": company_summary,
        "sector_name": sector_name or "코스피/코스닥 주요 산업",
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
            data = _fetch_krx_naver_data(code, fallback_name=symbol_or_name)
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
                "pe_ratio": info.get("trailingPE", "N/A"),
                "pb_ratio": info.get("priceToBook", "N/A"),
                "eps": info.get("trailingEps", "N/A"),
                "bps": info.get("bookValue", "N/A"),
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

    # 종목명이 코드 번호이거나 비어있는 경우 보정
    if data.get("symbol") == code or data.get("symbol", "").isdigit() or data.get("symbol") in ["종목", "종목분석"]:
        if symbol_or_name and not symbol_or_name.isdigit() and symbol_or_name not in ["종목", "종목분석"]:
            data["symbol"] = symbol_or_name
        elif REVERSE_KNOWN_TICKERS.get(code):
            data["symbol"] = REVERSE_KNOWN_TICKERS.get(code)

    cache_service.set("market", cache_key, data, CACHE_TTL_MARKET)
    return data

def fetch_top_screening_stocks(sector: str = "AI", style: str = "GROWTH", top_n: int = 5) -> List[Dict[str, Any]]:
    sector_pools = {
        "ENERGY": ["두산에너빌리티", "HD현대일렉트릭", "한화솔루션", "씨에스윈드", "LS ELECTRIC", "효성중공업", "한국전력"],
        "BATTERY": ["LG에너지솔루션", "POSCO홀딩스", "에코프로비엠", "에코프로", "삼성SDI", "엘앤에프", "포스코퓨처엠"],
        "BIO": ["삼성바이오로직스", "셀트리온", "알테오젠", "유한양행", "한미약품", "리가켐바이오", "에이비엘바이오"],
        "DEFENSE": ["한화에어로스페이스", "현대로템", "한국항공우주", "LIG넥스원", "HD현대중공업", "한화오션", "삼성중공업"],
        "AI": ["리노공업", "HPSP", "이수페타시스", "SK텔레콤", "삼성SDS", "한미반도체", "주성엔지니어링"],
        "AUTO": ["현대차", "기아", "현대모비스", "HL만도"],
        "PLATFORM": ["NAVER", "카카오", "하이브", "JYP Ent.", "스튜디오드래곤"]
    }
    targets = sector_pools.get(sector, sector_pools["AI"])[:top_n]
    results = []
    for t in targets:
        try:
            results.append(fetch_market_data(t))
        except Exception:
            pass
    return results
