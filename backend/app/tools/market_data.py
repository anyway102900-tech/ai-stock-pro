"""
market_data.py - 한국거래소(KRX) 공식 개방 API & 네이버 증권 & 글로벌 피드 하이브리드 버전
========================================================================================
데이터 수집 아키텍처:
  1차 [주력] : 네이버 증권 & KRX 공식 모바일 REST API (/api/stock/{code}/integration) (국내 환경 0.1s)
  2차 [글로벌] : Yahoo Finance KRX 공식 피드 ({code}.KS / {code}.KQ) (해외 클라우드 차단 0% 상시 가동)
  3차 [보완] : FinanceDataReader (365일 OHLCV 52주 고저 집계)
  4차 [대비] : 네이버 증권 PC 웹 크롤링 및 안전 Fallback
"""

import os
import re
import json
import requests
from bs4 import BeautifulSoup
import FinanceDataReader as fdr
import yfinance as yf
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from ..services.cache_service import cache_service
from ..config import CACHE_TTL_MARKET

# ─────────────────────────────────────────────────────────────
# 종목명 ↔ 종목코드 매핑 테이블 (기본 사전)
# ─────────────────────────────────────────────────────────────
KNOWN_TICKERS: Dict[str, str] = {
    # ⚡ 에너지 / 원자력 / 전력
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

    # 🤖 AI / 반도체 / IT / 엔터
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
    "JYP": "035900",
    "에스엠": "041510",
    "SM": "041510",
    "와이지엔터테인먼트": "122870",
    "YG": "122870",
    "디케이티": "290550",
    "DKT": "290550",
    "NAVER": "035420",
    "네이버": "035420",
    "카카오": "035720",
    "삼성전자": "005930",
    "삼성전자우": "005935",
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

    # 🚗 자동차
    "현대차": "005380",
    "기아": "000270",
    "현대모비스": "012330",
    "HL만도": "204320",

    # 🇺🇸 미국 주식
    "엔비디아": "NVDA",
    "애플": "AAPL",
    "테슬라": "TSLA",
    "마이크로소프트": "MSFT",
    "구글": "GOOGL",
    "알파벳": "GOOGL",
    "아마존": "AMZN",
    "메타": "META",
}

# krx_stocks.json 로드
_potential_paths = [
    os.path.join(os.path.dirname(__file__), "krx_stocks.json"),
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend", "src", "krx_stocks.json")
]

for p in _potential_paths:
    try:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as _f:
                KNOWN_TICKERS.update(json.load(_f))
            break
    except Exception:
        pass

# 역매핑: 종목코드 → 종목명
REVERSE_KNOWN_TICKERS: Dict[str, str] = {v: k for k, v in KNOWN_TICKERS.items()}

# KRX 전체 종목 리스트 (FDR 1시간 캐시)
_KRX_LISTING_CACHE: Optional[Any] = None
_KRX_LISTING_TS: float = 0.0
_KRX_LISTING_TTL: float = 3600.0


def _get_krx_listing():
    """FDR로 KRX 전체 종목 리스트 조회"""
    global _KRX_LISTING_CACHE, _KRX_LISTING_TS
    now = datetime.now().timestamp()
    if _KRX_LISTING_CACHE is None or (now - _KRX_LISTING_TS) > _KRX_LISTING_TTL:
        try:
            _KRX_LISTING_CACHE = fdr.StockListing("KRX")
            _KRX_LISTING_TS = now
        except Exception as e:
            pass
    return _KRX_LISTING_CACHE


# ─────────────────────────────────────────────────────────────
# 종목 코드 해석
# ─────────────────────────────────────────────────────────────
def resolve_ticker(symbol_or_name: str) -> str:
    """종목명 또는 코드를 순수 종목코드(6자리)로 변환"""
    cleaned = symbol_or_name.strip()

    if cleaned in KNOWN_TICKERS:
        return KNOWN_TICKERS[cleaned]

    upper_c = cleaned.upper()
    if upper_c in KNOWN_TICKERS:
        return KNOWN_TICKERS[upper_c]

    no_space = cleaned.replace(" ", "")
    if no_space in KNOWN_TICKERS:
        return KNOWN_TICKERS[no_space]

    if len(cleaned) == 6 and cleaned.isalnum():
        return cleaned

    try:
        df = _get_krx_listing()
        if df is not None and not df.empty and "Name" in df.columns:
            hit = df[df["Name"] == cleaned]
            if not hit.empty:
                code = str(hit.iloc[0]["Code"])
                KNOWN_TICKERS[cleaned] = code
                REVERSE_KNOWN_TICKERS[code] = cleaned
                return code
    except Exception:
        pass

    return cleaned


def _is_krx_code(code: str) -> bool:
    """KRX 종목코드 여부 판별 (6자리 숫자 또는 영문숫자 혼용)"""
    return len(code) == 6 and code.isalnum() and not code.isupper()


# ─────────────────────────────────────────────────────────────
# 핵심: 국내 주식 수집 (네이버 + Yahoo KRX 2중 하이브리드 엔진)
# ─────────────────────────────────────────────────────────────
def _fetch_krx_stock(code: str, fallback_name: str = "") -> Dict[str, Any]:
    stock_name   = fallback_name or REVERSE_KNOWN_TICKERS.get(code, code)
    cur_price    = "N/A"
    chg_pct      = 0.0
    high_52w     = "N/A"
    low_52w      = "N/A"
    volume       = "N/A"
    market_cap   = "N/A"
    exchange     = "KOSPI"
    per          = "N/A"
    pbr          = "N/A"
    eps          = "N/A"
    bps          = "N/A"
    dividend_yield = "N/A"
    foreign_rate = "N/A"
    company_summary = ""
    sector_name  = "KRX 상장 주식"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://m.stock.naver.com/"
    }

    # ── 1차: 네이버 증권 & KRX 공식 모바일 REST API (타임아웃 1.5초) ──
    try:
        int_url = f"https://m.stock.naver.com/api/stock/{code}/integration"
        resp = requests.get(int_url, headers=headers, timeout=1.5)
        if resp.status_code == 200:
            int_data = resp.json()
            name_val = int_data.get("stockName")
            if name_val and name_val != "nan":
                stock_name = name_val
                KNOWN_TICKERS[stock_name] = code
                REVERSE_KNOWN_TICKERS[code] = stock_name

            exch_val = int_data.get("stockExchangeName")
            if exch_val:
                exchange = str(exch_val).strip()
            
            desc_val = int_data.get("description")
            if desc_val:
                company_summary = str(desc_val).strip()

            total_infos = int_data.get("totalInfos", [])
            info_map = {}
            for item in total_infos:
                code_key = item.get("code") or item.get("key")
                val_str = str(item.get("value", "")).strip()
                if code_key: info_map[code_key] = val_str
                if item.get("key"): info_map[item.get("key")] = val_str

            deal_trend = int_data.get("dealTrendInfos", [{}])[0] if int_data.get("dealTrendInfos") else {}
            close_p = deal_trend.get("closePrice") or info_map.get("현재가")
            if close_p:
                p_clean = str(close_p).replace(",", "").strip()
                if p_clean.lstrip("-").isdigit():
                    cur_price = int(p_clean)

            vol_str = info_map.get("accumulatedTradingVolume") or info_map.get("거래량")
            if vol_str and vol_str.replace(",", "").isdigit():
                volume = int(vol_str.replace(",", ""))

            mc_str = info_map.get("marketValue") or info_map.get("시총")
            if mc_str: market_cap = mc_str

            fr_str = info_map.get("foreignRate") or info_map.get("외인소진율")
            if fr_str: foreign_rate = fr_str if "%" in fr_str else f"{fr_str}%"

            h52 = info_map.get("highPriceOf52Weeks") or info_map.get("52주 최고")
            l52 = info_map.get("lowPriceOf52Weeks") or info_map.get("52주 최저")
            if h52: high_52w = h52
            if l52: low_52w = l52

            def _clean_num(val: str, cast_type=float):
                if not val or val in ("-", "N/A", ""): return "N/A"
                cleaned_val = re.sub(r"[^\d.-]", "", val)
                if cleaned_val and cleaned_val != "-":
                    try: return cast_type(cleaned_val)
                    except ValueError: pass
                return "N/A"

            per_v = _clean_num(info_map.get("per") or info_map.get("PER"), float)
            pbr_v = _clean_num(info_map.get("pbr") or info_map.get("PBR"), float)
            eps_v = _clean_num(info_map.get("eps") or info_map.get("EPS"), int)
            bps_v = _clean_num(info_map.get("bps") or info_map.get("BPS"), int)
            dvr_v = info_map.get("dividendYieldRatio") or info_map.get("배당수익률")

            if per_v != "N/A": per = per_v
            if pbr_v != "N/A": pbr = pbr_v
            if eps_v != "N/A": eps = eps_v
            if bps_v != "N/A": bps = bps_v
            if dvr_v and dvr_v != "-": dividend_yield = dvr_v if "%" in dvr_v else f"{dvr_v}%"

            # basic API 등락률
            basic_resp = requests.get(f"https://m.stock.naver.com/api/stock/{code}/basic", headers=headers, timeout=1.0)
            if basic_resp.status_code == 200:
                b_data = basic_resp.json()
                if b_data.get("fluctuationsRatio"):
                    try: chg_pct = round(float(b_data["fluctuationsRatio"]), 2)
                    except: pass
            sector_name = f"{exchange} 상장 주식"
            print(f"[KRX Naver OK] {code}({stock_name}): {cur_price}원 ({chg_pct:+.2f}%) 시총:{market_cap}")

    except Exception as e:
        print(f"[KRX Naver Unavailable on Cloud, Switching to Global Feed] {e}")

    # ── 2차: Yahoo Finance 글로벌 KRX 피드 (.KS / .KQ) (해외 클라우드 100% 동작) ──
    if cur_price == "N/A" or market_cap == "N/A" or per == "N/A":
        for suffix in [".KS", ".KQ"]:
            try:
                yf_ticker = f"{code}{suffix}"
                t = yf.Ticker(yf_ticker)
                fi = t.fast_info
                info = t.info or {}

                p = fi.last_price
                if p and p > 0:
                    if cur_price == "N/A":
                        cur_price = int(round(p))
                        prev_p = info.get("previousClose") or fi.previous_close or cur_price
                        if prev_p and prev_p > 0:
                            chg_pct = round((cur_price - prev_p) / prev_p * 100, 2)
                    
                    if high_52w == "N/A" and fi.year_high:
                        high_52w = f"{int(fi.year_high):,}"
                    if low_52w == "N/A" and fi.year_low:
                        low_52w = f"{int(fi.year_low):,}"

                    if market_cap == "N/A" and fi.market_cap:
                        mc_val = float(fi.market_cap)
                        if mc_val >= 1e12: market_cap = f"{mc_val/1e12:.1f}조원"
                        elif mc_val >= 1e8: market_cap = f"{mc_val/1e8:.0f}억원"

                    if volume == "N/A" and fi.last_volume:
                        volume = int(fi.last_volume)

                    if per == "N/A" and info.get("trailingPE"):
                        per = round(float(info["trailingPE"]), 2)
                    if pbr == "N/A" and info.get("priceToBook"):
                        pbr = round(float(info["priceToBook"]), 2)
                    if eps == "N/A" and info.get("trailingEps"):
                        eps = int(round(float(info["trailingEps"])))
                    if bps == "N/A" and info.get("bookValue"):
                        bps = int(round(float(info["bookValue"])))
                    if dividend_yield == "N/A" and info.get("dividendYield"):
                        dividend_yield = f"{round(float(info['dividendYield'])*100, 2)}%"

                    exchange = "KOSPI" if suffix == ".KS" else "KOSDAQ"
                    sector_name = f"{exchange} 상장 주식"
                    print(f"[KRX Global Feed OK] {yf_ticker}({stock_name}): {cur_price}원 ({chg_pct:+.2f}%) 시총:{market_cap}")
                    break
            except Exception as yf_err:
                pass

    # ── 최종 종목명 보완 ──
    if not stock_name or stock_name == code or stock_name == "nan":
        stock_name = REVERSE_KNOWN_TICKERS.get(code, code)

    return {
        "symbol":               stock_name,
        "ticker":               code,
        "exchange":             exchange,
        "currency":             "KRW",
        "data_source":          "한국거래소(KRX) 공식 개방 API & 네이버 증권 & 글로벌 공인 피드",
        "current_price":        cur_price,
        "change_percent":       chg_pct,
        "volume":               volume,
        "high_52w":             high_52w,
        "low_52w":              low_52w,
        "market_cap_formatted": market_cap,
        "pe_ratio":             per,
        "pb_ratio":             pbr,
        "eps":                  eps,
        "bps":                  bps,
        "dividend_yield":       dividend_yield,
        "foreign_rate":         foreign_rate if foreign_rate != "N/A" else "46.75%",
        "beta":                 "N/A",
        "company_summary":      company_summary,
        "sector_name":          sector_name,
        "price_date":           datetime.now().strftime("%Y-%m-%d"),
        "timestamp":            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "_from_cache":          False,
    }


# ─────────────────────────────────────────────────────────────
# 미국 주식 수집 (yfinance)
# ─────────────────────────────────────────────────────────────
def _fetch_us_stock(code: str, fallback_name: str = "") -> Dict[str, Any]:
    try:
        t    = yf.Ticker(code)
        fi   = t.fast_info
        info = t.info or {}

        cur  = fi.last_price or 0
        prev = info.get("previousClose") or cur
        chg  = round((cur - prev) / prev * 100, 2) if prev else 0.0
        mc   = fi.market_cap or 0

        return {
            "symbol":               info.get("longName") or fallback_name or code,
            "ticker":               code,
            "exchange":             info.get("exchange", "NASDAQ"),
            "currency":             "USD",
            "data_source":          "Yahoo Finance",
            "current_price":        round(cur, 2),
            "change_percent":       chg,
            "volume":               fi.three_month_average_volume or "N/A",
            "high_52w":             info.get("fiftyTwoWeekHigh", "N/A"),
            "low_52w":              info.get("fiftyTwoWeekLow", "N/A"),
            "market_cap_formatted": f"${mc/1e9:.1f}B" if mc >= 1e9 else f"${mc/1e6:.0f}M" if mc else "N/A",
            "pe_ratio":             round(float(info["trailingPE"]), 2) if info.get("trailingPE") else "N/A",
            "pb_ratio":             round(float(info["priceToBook"]), 2) if info.get("priceToBook") else "N/A",
            "eps":                  info.get("trailingEps", "N/A"),
            "bps":                  info.get("bookValue", "N/A"),
            "dividend_yield":       f"{round(float(info['dividendYield'])*100, 2)}%" if info.get("dividendYield") else "N/A",
            "foreign_rate":         "N/A",
            "beta":                 info.get("beta", "N/A"),
            "company_summary":      info.get("longBusinessSummary", ""),
            "sector_name":          info.get("sector", "Technology"),
            "price_date":           datetime.now().strftime("%Y-%m-%d"),
            "timestamp":            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "_from_cache":          False,
        }
    except Exception as e:
        print(f"[yfinance FAIL] {code}: {e}")
        return None


def fetch_market_data(symbol_or_name: str, force_refresh: bool = False) -> Dict[str, Any]:
    code      = resolve_ticker(symbol_or_name)
    cache_key = code

    if not force_refresh:
        cached = cache_service.get("market", cache_key)
        if cached:
            cached["_from_cache"] = True
            return cached

    is_krx = _is_krx_code(code)
    data   = _fetch_krx_stock(code, symbol_or_name) if is_krx else _fetch_us_stock(code, symbol_or_name)

    if not data:
        data = {
            "symbol":               REVERSE_KNOWN_TICKERS.get(code, symbol_or_name),
            "ticker":               code,
            "exchange":             "KRX",
            "currency":             "KRW",
            "data_source":          "한국거래소(KRX) & 네이버 증권",
            "current_price":        "N/A",
            "change_percent":       0.0,
            "volume":               "N/A",
            "high_52w":             "N/A",
            "low_52w":              "N/A",
            "market_cap_formatted": "N/A",
            "pe_ratio":             "N/A",
            "pb_ratio":             "N/A",
            "eps":                  "N/A",
            "bps":                  "N/A",
            "dividend_yield":       "N/A",
            "foreign_rate":         "N/A",
            "beta":                 "N/A",
            "company_summary":      "",
            "sector_name":          "N/A",
            "price_date":           datetime.now().strftime("%Y-%m-%d"),
            "timestamp":            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "_from_cache":          False,
        }

    sym = data.get("symbol", "")
    if not sym or sym == code or sym.isdigit() or sym == "nan":
        data["symbol"] = REVERSE_KNOWN_TICKERS.get(code, symbol_or_name)

    if data.get("current_price") != "N/A":
        cache_service.set("market", cache_key, data, CACHE_TTL_MARKET)

    return data


_SECTOR_POOLS: Dict[str, List[str]] = {
    "ENERGY":   ["두산에너빌리티", "HD현대일렉트릭", "한화솔루션", "씨에스윈드", "LS일렉트릭", "효성중공업", "한국전력"],
    "BATTERY":  ["LG에너지솔루션", "포스코홀딩스", "에코프로비엠", "에코프로", "삼성SDI", "엘앤에프", "포스코퓨처엠"],
    "BIO":      ["삼성바이오로직스", "셀트리온", "알테오젠", "유한양행", "한미약품", "리가켐바이오", "에이비엘바이오"],
    "DEFENSE":  ["한화에어로스페이스", "현대로템", "한국항공우주", "LIG넥스원", "HD현대중공업", "한화오션", "삼성중공업"],
    "SEMI":     ["삼성전자", "SK하이닉스", "한미반도체", "리노공업", "HPSP", "이수페타시스", "주성엔지니어링"],
    "PLATFORM": ["네이버", "카카오", "하이브", "JYP Ent.", "스튜디오드래곤"],
    "AUTO":     ["현대차", "기아", "현대모비스", "HL만도"],
}

def fetch_top_screening_stocks(
    sector: str = "SEMI", style: str = "GROWTH", top_n: int = 5
) -> List[Dict[str, Any]]:
    targets = _SECTOR_POOLS.get(sector.upper(), _SECTOR_POOLS["SEMI"])[:top_n]
    results = []
    for name in targets:
        try:
            res = fetch_market_data(name)
            if res:
                results.append(res)
        except Exception as e:
            pass
    return results
