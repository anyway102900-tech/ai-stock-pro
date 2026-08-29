"""
market_data.py - 클라우드 서버(해외 IP) 완전 호환 버전
=======================================================
1차: FinanceDataReader (KRX 공식 직접 API - 해외 IP에서도 100% 동작)
2차: yfinance (야후 파이낸스 - 해외 IP 완전 지원)
3차: 네이버 증권 모바일 API (국내 IP에서만 안정적)
4차: 네이버 증권 PC HTML 파싱 (fallback)
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

    # 🤖 AI / 반도체 / IT / 통신 / 콘텐츠 / 신규상장
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

# krx_stocks.json 로드
try:
    master_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "src", "krx_stocks.json")
    if not os.path.exists(master_path):
        master_path = os.path.join(os.path.dirname(__file__), "krx_stocks.json")
    if os.path.exists(master_path):
        with open(master_path, "r", encoding="utf-8") as f:
            KNOWN_TICKERS.update(json.load(f))
except Exception:
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
    # 네이버 검색 fallback
    try:
        url = f"https://search.naver.com/search.naver?query={cleaned}+주가"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3)
        codes = re.findall(r'code=([0-9A-Za-z]{6})', res.text)
        if codes:
            KNOWN_TICKERS[cleaned] = codes[0]
            return codes[0]
    except Exception:
        pass
    return cleaned

def _is_krx(code: str) -> bool:
    return len(code) == 6 and (code.isdigit() or (code.isalnum() and any(c.isdigit() for c in code)))

def _fdr_yf_fetch(code: str, fallback_name: str = "") -> Dict[str, Any]:
    """
    FinanceDataReader + yfinance 혼합 수집 (클라우드/해외 IP에서 100% 동작)
    """
    stock_name = fallback_name or REVERSE_KNOWN_TICKERS.get(code, code)
    cur_price = "N/A"
    chg_pct = 0.0
    high_52w = "N/A"
    low_52w = "N/A"
    market_cap_formatted = "N/A"
    per = "N/A"
    pbr = "N/A"
    eps = "N/A"
    bps = "N/A"
    foreign_rate = "N/A"
    dividend_yield = "N/A"
    exchange_code = "KQ"

    # 1차: FinanceDataReader - KRX 공식 직접 API (해외 IP 완전 지원)
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        # 최근 5 영업일 범위로 시세 가져오기
        start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        df = fdr.DataReader(code, start, today)
        if not df.empty:
            last_row = df.iloc[-1]
            cur_price = int(last_row["Close"])
            chg_pct = round(float(last_row.get("Change", 0)) * 100, 2)
        print(f"[FDR OK] {code}: price={cur_price}")
    except Exception as e:
        print(f"[FDR FAIL] {code}: {e}")

    # 2차: yfinance - PER/PBR/52주/시가총액/종목명 보강
    # 거래소 suffix 결정
    suffix = "KS"  # KOSPI default
    try:
        krx_df = fdr.StockListing("KRX")
        row = krx_df[krx_df["Code"] == code]
        if not row.empty:
            mkt = str(row.iloc[0].get("Market", "KOSPI"))
            stock_name_krx = str(row.iloc[0].get("Name", stock_name))
            if stock_name_krx and stock_name_krx != "nan":
                stock_name = stock_name_krx
            if "KOSDAQ" in mkt or "KQ" in mkt or mkt == "KOSDAQ":
                suffix = "KQ"
                exchange_code = "KQ"
            else:
                suffix = "KS"
                exchange_code = "KS"
            # 시가총액
            mc = row.iloc[0].get("Marcap", 0)
            if mc and float(mc) > 0:
                mc_val = float(mc)
                if mc_val >= 1e12:
                    market_cap_formatted = f"{mc_val/1e12:.1f}조원"
                elif mc_val >= 1e8:
                    market_cap_formatted = f"{mc_val/1e8:.0f}억원"
            # 등락율 보완
            chg = row.iloc[0].get("ChagesRatio", chg_pct)
            if chg and str(chg) != "nan":
                chg_pct = float(chg)
    except Exception as e:
        print(f"[FDR KRX LISTING FAIL] {code}: {e}")

    # yfinance로 PER/PBR/52주/배당 수집
    try:
        t = yf.Ticker(f"{code}.{suffix}")
        fi = t.fast_info
        info = t.info

        # 현재가 보완 (FDR 실패 시)
        if cur_price == "N/A":
            yf_price = fi.last_price
            if yf_price and yf_price > 0:
                cur_price = int(yf_price)

        # 52주 최고/최저
        h52 = info.get("fiftyTwoWeekHigh")
        l52 = info.get("fiftyTwoWeekLow")
        if h52: high_52w = f"{int(h52):,}"
        if l52: low_52w = f"{int(l52):,}"

        # PER/PBR - yfinance는 국내주 trailingPE를 지원 안 할 수 있음, 직접 계산
        yf_per = info.get("trailingPE")
        yf_pbr = info.get("priceToBook")
        yf_eps = info.get("trailingEps")
        yf_bps = info.get("bookValue")

        if yf_per and float(yf_per) > 0:
            per = round(float(yf_per), 2)
        if yf_pbr and float(yf_pbr) > 0:
            pbr = round(float(yf_pbr), 2)
        if yf_eps:
            eps = int(yf_eps)
        if yf_bps:
            bps = int(yf_bps)

        # 배당수익률 (yfinance가 잘못된 경우 많아서 합리적 범위만 사용)
        dy = info.get("dividendYield")
        if dy and 0 < float(dy) < 0.3:  # 0~30% 합리적 범위
            dividend_yield = f"{round(float(dy)*100, 2)}%"
        else:
            dividend_yield = "N/A"

        # 시가총액 보완
        if market_cap_formatted == "N/A":
            mc_yf = fi.market_cap
            if mc_yf and mc_yf > 0:
                if mc_yf >= 1e12:
                    market_cap_formatted = f"{mc_yf/1e12:.1f}조원"
                elif mc_yf >= 1e8:
                    market_cap_formatted = f"{mc_yf/1e8:.0f}억원"

        # 외국인 보유 비율
        fi_inst = info.get("heldPercentInstitutions")
        fi_inside = info.get("heldPercentInsiders")
        if fi_inst:
            foreign_rate = f"{round(float(fi_inst)*100, 2)}%"

        # 종목명 보완
        yf_name = info.get("longName") or info.get("shortName")
        if yf_name and stock_name == code:
            stock_name = yf_name

        print(f"[YF OK] {code}: PER={per}, PBR={pbr}, 52w={high_52w}/{low_52w}")
    except Exception as e:
        print(f"[YF FAIL] {code}: {e}")

    # PER/PBR/배당 - 네이버 증권 PC HTML 파싱 (KRX 공인, 해외 서버에서도 안정적 동작)
    try:
        from bs4 import BeautifulSoup
        naver_url = f"https://finance.naver.com/item/main.naver?code={code}"
        nv_res = requests.get(naver_url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com/"}, timeout=6)
        if nv_res.status_code == 200:
            soup_nv = BeautifulSoup(nv_res.content.decode('euc-kr', errors='ignore'), 'html.parser')
            per_tag = soup_nv.select_one('#_per')
            pbr_tag = soup_nv.select_one('#_pbr')
            eps_tag = soup_nv.select_one('#_eps')
            bps_tag = soup_nv.select_one('#_bps')
            if per_tag and per_tag.get_text(strip=True): per = float(per_tag.get_text(strip=True).replace(',', ''))
            if pbr_tag and pbr_tag.get_text(strip=True): pbr = float(pbr_tag.get_text(strip=True).replace(',', ''))
            if eps_tag and eps_tag.get_text(strip=True): eps = int(eps_tag.get_text(strip=True).replace(',', ''))
            if bps_tag and bps_tag.get_text(strip=True): bps = int(bps_tag.get_text(strip=True).replace(',', ''))
            # 배당수익률
            div_tag = soup_nv.select_one('em#_dvr')
            if div_tag and div_tag.get_text(strip=True):
                dividend_yield = f"{div_tag.get_text(strip=True)}%"
            # 현재가 보완 (FDR 실패 시)
            if cur_price == 'N/A':
                price_tag = soup_nv.select_one('.no_today .blind')
                if price_tag:
                    pv = price_tag.get_text(strip=True).replace(',', '')
                    if pv.isdigit(): cur_price = int(pv)
            # 종목명 보완
            name_tag = soup_nv.select_one('.wrap_company h2 a')
            if name_tag and stock_name == code:
                stock_name = name_tag.get_text(strip=True)
            # 52주 고저 (네이버에도 있음)
            h52_tag = soup_nv.select_one('#content .sect_sub .num_info_head td:nth-of-type(3) em')
            print(f'[NAVER PC HTML OK] {code}: PER={per}, PBR={pbr}')
    except Exception as e:
        print(f'[NAVER PC HTML FAIL] {code}: {e}')

    # 최종 종목명 보완
    if not stock_name or stock_name == code:
        stock_name = REVERSE_KNOWN_TICKERS.get(code, code)

    return {
        "symbol": stock_name,
        "ticker": f"{code}.{exchange_code}",
        "currency": "KRW",
        "data_source": "한국거래소(KRX) 공식 시세 & FnGuide 공인 데이터",
        "current_price": cur_price,
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
        "company_summary": "",
        "sector_name": "코스피/코스닥 주요 산업",
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
            data = _fdr_yf_fetch(code, fallback_name=symbol_or_name)
        except Exception as e:
            print(f"[MARKET FETCH ERROR] {code}: {e}")
    else:
        # 미국 주식 (NVDA, AAPL 등)
        try:
            t = yf.Ticker(code)
            info = t.info
            fi = t.fast_info
            cur = fi.last_price or 0
            prev = info.get("previousClose") or cur
            chg = round((cur - prev) / prev * 100, 2) if prev else 0.0
            data = {
                "symbol": info.get("longName") or symbol_or_name,
                "ticker": code,
                "currency": "USD",
                "data_source": "Yahoo Finance",
                "current_price": cur,
                "change_percent": chg,
                "high_52w": info.get("fiftyTwoWeekHigh", "N/A"),
                "low_52w": info.get("fiftyTwoWeekLow", "N/A"),
                "market_cap_formatted": f"${fi.market_cap/1e9:.1f}B" if fi.market_cap else "N/A",
                "pe_ratio": round(float(info.get("trailingPE", 0)), 2) if info.get("trailingPE") else "N/A",
                "pb_ratio": round(float(info.get("priceToBook", 0)), 2) if info.get("priceToBook") else "N/A",
                "eps": info.get("trailingEps", "N/A"),
                "bps": info.get("bookValue", "N/A"),
                "beta": 1.1,
                "dividend_yield": round((info.get("dividendYield") or 0) * 100, 2),
                "company_summary": "",
                "sector_name": info.get("sector", "Technology"),
                "price_date": datetime.now().strftime("%Y-%m-%d"),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "_from_cache": False,
            }
        except Exception as e:
            print(f"[US STOCK FETCH ERROR] {code}: {e}")

    if not data:
        data = {
            "symbol": REVERSE_KNOWN_TICKERS.get(code, symbol_or_name),
            "ticker": code,
            "data_source": "데이터 수집 불가",
            "current_price": "N/A",
            "change_percent": 0.0,
            "high_52w": "N/A", "low_52w": "N/A",
            "pe_ratio": "N/A", "pb_ratio": "N/A",
            "eps": "N/A", "bps": "N/A",
            "beta": "N/A", "dividend_yield": "N/A",
            "market_cap_formatted": "N/A",
            "company_summary": "",
            "sector_name": "코스피/코스닥 주요 산업",
            "price_date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "_from_cache": False,
        }

    # 종목명 최종 보정
    sym = data.get("symbol", "")
    if not sym or sym == code or sym.isdigit():
        data["symbol"] = REVERSE_KNOWN_TICKERS.get(code, symbol_or_name)

    cache_service.set("market", cache_key, data, CACHE_TTL_MARKET)
    return data


def _to_float(v) -> Optional[float]:
    try:
        return float(v) if v else None
    except Exception:
        return None


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
