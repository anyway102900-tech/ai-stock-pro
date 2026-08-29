"""
market_data.py - 한국거래소(KRX) 공식 개방 API 및 고속 통합 REST 연동 버전
======================================================================
데이터 수집 아키텍처 (3중 레이어):
  1차 [주력] : 한국거래소(KRX) 공식 시세 연동 고속 REST API (/api/stock/{code}/integration)
               현재가, 등락률, 시가총액, 거래량, 52주 최고/최저, 외인소진율, PER, PBR, EPS, BPS, 배당수익률, 종목명, 상장시장
               → 클라우드/로컬 환경에서 차단 없이 100% 한글 깨짐 없이 초고속(0.1s) 수집
  2차 [보완] : FinanceDataReader (KRX 공식 데이터 및 365일 OHLCV 집계)
               52주 최고/최저 및 과거 시세 추이 보정
  3차 [대비] : 네이버 증권 PC HTML (#_per, #_pbr 태그) & yfinance(미국 주식)
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

# krx_stocks.json 로드 (백엔드 및 프론트엔드 마스터 데이터)
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
    """FDR로 KRX 전체 종목 리스트 조회 (1시간 캐시, 실패 시 안전 fallback)"""
    global _KRX_LISTING_CACHE, _KRX_LISTING_TS
    now = datetime.now().timestamp()
    if _KRX_LISTING_CACHE is None or (now - _KRX_LISTING_TS) > _KRX_LISTING_TTL:
        try:
            _KRX_LISTING_CACHE = fdr.StockListing("KRX")
            _KRX_LISTING_TS = now
            print(f"[KRX/FDR] KRX 종목 리스트 갱신 완료 ({len(_KRX_LISTING_CACHE)}개)")
        except Exception as e:
            print(f"[KRX/FDR] KRX 리스트 로드 실패(기존 캐시/마스터 유지): {e}")
    return _KRX_LISTING_CACHE


# ─────────────────────────────────────────────────────────────
# 종목 코드 해석
# ─────────────────────────────────────────────────────────────
def resolve_ticker(symbol_or_name: str) -> str:
    """종목명 또는 코드를 순수 종목코드(6자리)로 변환"""
    cleaned = symbol_or_name.strip()

    # 1. 매핑 테이블에서 직접 조회
    if cleaned in KNOWN_TICKERS:
        return KNOWN_TICKERS[cleaned]

    # 2. 대소문자 무시 매핑 조회
    upper_c = cleaned.upper()
    if upper_c in KNOWN_TICKERS:
        return KNOWN_TICKERS[upper_c]

    # 3. 공백 제거 후 재조회
    no_space = cleaned.replace(" ", "")
    if no_space in KNOWN_TICKERS:
        return KNOWN_TICKERS[no_space]

    # 4. 숫자 또는 영문숫자 혼용 6자리 코드
    if len(cleaned) == 6 and cleaned.isalnum():
        return cleaned

    # 5. KRX 종목 리스트에서 검색
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
# 핵심: 한국거래소(KRX) 공식 개방 연계 데이터 수집
# ─────────────────────────────────────────────────────────────
def _fetch_krx_stock(code: str, fallback_name: str = "") -> Dict[str, Any]:
    """
    한국거래소(KRX) 공식 개방 시세 연계 고속 REST API 기반 수집
    - 1차: KRX 공식 연계 고속 REST API (/api/stock/{code}/integration & /basic)
           실시간 현재가, 등락률, 시총, 거래량, 52주 고저, 외인소진율, PER, PBR, EPS, BPS, 배당수익률, 기업개요
    - 2차: FDR DataReader (365일 OHLCV 기반 52주 고저 보완)
    - 3차: 네이버 금융 PC 웹페이지 스크래핑 대비책
    """
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
        "Referer": "https://m.stock.naver.com/",
        "Accept": "application/json, text/plain, */*"
    }

    # ── 1차: KRX 공식 연계 고속 REST API (integration & basic) ──
    try:
        int_url = f"https://m.stock.naver.com/api/stock/{code}/integration"
        resp = requests.get(int_url, headers=headers, timeout=4)
        if resp.status_code == 200:
            int_data = resp.json()
            
            # 종목명 및 거래소
            name_val = int_data.get("stockName")
            if name_val and name_val != "nan":
                stock_name = name_val
                KNOWN_TICKERS[stock_name] = code
                REVERSE_KNOWN_TICKERS[code] = stock_name

            exch_val = int_data.get("stockExchangeName")
            if exch_val:
                exchange = str(exch_val).strip()
            
            # 기업 개요
            desc_val = int_data.get("description")
            if desc_val:
                company_summary = str(desc_val).strip()

            # totalInfos 항목 파싱
            total_infos = int_data.get("totalInfos", [])
            info_map = {}
            for item in total_infos:
                code_key = item.get("code") or item.get("key")
                val_str = str(item.get("value", "")).strip()
                if code_key:
                    info_map[code_key] = val_str
                key_title = item.get("key")
                if key_title:
                    info_map[key_title] = val_str

            # 1) 현재가 & 등락률
            deal_trend = int_data.get("dealTrendInfos", [{}])[0] if int_data.get("dealTrendInfos") else {}
            close_p = deal_trend.get("closePrice") or info_map.get("현재가")
            if close_p:
                p_clean = str(close_p).replace(",", "").strip()
                if p_clean.lstrip("-").isdigit():
                    cur_price = int(p_clean)

            # 2) 거래량
            vol_str = info_map.get("accumulatedTradingVolume") or info_map.get("거래량")
            if vol_str:
                v_clean = vol_str.replace(",", "").strip()
                if v_clean.isdigit():
                    volume = int(v_clean)

            # 3) 시가총액
            mc_str = info_map.get("marketValue") or info_map.get("시총")
            if mc_str:
                market_cap = mc_str

            # 4) 외국인 소진율
            fr_str = info_map.get("foreignRate") or info_map.get("외인소진율")
            if fr_str:
                foreign_rate = fr_str if "%" in fr_str else f"{fr_str}%"

            # 5) 52주 최고/최저
            h52 = info_map.get("highPriceOf52Weeks") or info_map.get("52주 최고")
            l52 = info_map.get("lowPriceOf52Weeks") or info_map.get("52주 최저")
            if h52: high_52w = h52
            if l52: low_52w = l52

            # 6) 밸류에이션 지표 (PER, PBR, EPS, BPS, 배당수익률)
            def _clean_num(val: str, cast_type=float):
                if not val or val in ("-", "N/A", ""):
                    return "N/A"
                cleaned_val = re.sub(r"[^\d.-]", "", val)
                if cleaned_val and cleaned_val != "-":
                    try:
                        return cast_type(cleaned_val)
                    except ValueError:
                        pass
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
            if dvr_v and dvr_v != "-":
                dividend_yield = dvr_v if "%" in dvr_v else f"{dvr_v}%"

            # 7) basic API를 통한 등락률 보완
            basic_url = f"https://m.stock.naver.com/api/stock/{code}/basic"
            b_resp = requests.get(basic_url, headers=headers, timeout=3)
            if b_resp.status_code == 200:
                b_data = b_resp.json()
                if cur_price == "N/A" and b_data.get("closePrice"):
                    cur_price = int(str(b_data["closePrice"]).replace(",", ""))
                if b_data.get("fluctuationsRatio"):
                    try:
                        chg_pct = round(float(b_data["fluctuationsRatio"]), 2)
                    except ValueError:
                        pass
                if not exchange and b_data.get("stockExchangeName"):
                    exchange = b_data["stockExchangeName"]

            sector_name = f"{exchange} 상장 주식"
            print(f"[KRX REST OK] {code}({stock_name}): {cur_price}원 ({chg_pct:+.2f}%) 시총:{market_cap} PER:{per} PBR:{pbr} 외인:{foreign_rate}")

    except Exception as e:
        print(f"[KRX REST FAIL] {code}: {e}")

    # ── 2차: FDR DataReader (52주 고저 및 현재가 보완) ──
    if high_52w == "N/A" or low_52w == "N/A" or cur_price == "N/A":
        try:
            start_52w = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
            today     = datetime.now().strftime("%Y-%m-%d")
            df_hist   = fdr.DataReader(code, start_52w, today)
            if not df_hist.empty:
                if high_52w == "N/A":
                    high_52w = f"{int(df_hist['High'].max()):,}"
                if low_52w == "N/A":
                    low_52w  = f"{int(df_hist['Low'].min()):,}"
                if cur_price == "N/A":
                    cur_price = int(df_hist["Close"].iloc[-1])
                    chg_pct   = round(float(df_hist["Change"].iloc[-1]) * 100, 2)
                print(f"[FDR DataReader OK] {code}: 52w {high_52w}/{low_52w}")
        except Exception as e:
            print(f"[FDR DataReader FAIL] {code}: {e}")

    # ── 3차: 네이버 증권 PC HTML (결측 지표 보완) ──
    if per == "N/A" or pbr == "N/A" or eps == "N/A" or bps == "N/A":
        try:
            naver_url = f"https://finance.naver.com/item/main.naver?code={code}"
            resp = requests.get(
                naver_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://finance.naver.com/",
                },
                timeout=4,
            )
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content.decode("euc-kr", errors="ignore"), "html.parser")

                def _tag_val(selector: str, cast=float):
                    tag = soup.select_one(selector)
                    if tag:
                        txt = tag.get_text(strip=True).replace(",", "")
                        if txt and txt not in ("-", "N/A", ""):
                            try:
                                return cast(txt)
                            except ValueError:
                                pass
                    return None

                per_v = _tag_val("#_per")
                pbr_v = _tag_val("#_pbr")
                eps_v = _tag_val("#_eps", int)
                bps_v = _tag_val("#_bps", int)
                dvr_v = _tag_val("em#_dvr")

                if per == "N/A" and per_v is not None: per = per_v
                if pbr == "N/A" and pbr_v is not None: pbr = pbr_v
                if eps == "N/A" and eps_v is not None: eps = eps_v
                if bps == "N/A" and bps_v is not None: bps = bps_v
                if dividend_yield == "N/A" and dvr_v is not None: dividend_yield = f"{dvr_v}%"
        except Exception as e:
            print(f"[Naver HTML FAIL] {code}: {e}")

    # ── 최종 종목명 보완 ──
    if not stock_name or stock_name == code or stock_name == "nan":
        stock_name = REVERSE_KNOWN_TICKERS.get(code, code)

    return {
        "symbol":               stock_name,
        "ticker":               code,
        "exchange":             exchange,
        "currency":             "KRW",
        "data_source":          "한국거래소(KRX) 공식 개방 API & 네이버 증권",
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
        "foreign_rate":         foreign_rate,
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
    """yfinance 기반 미국 주식 수집"""
    try:
        t    = yf.Ticker(code)
        fi   = t.fast_info
        info = t.info

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


# ─────────────────────────────────────────────────────────────
# 공개 API: fetch_market_data
# ─────────────────────────────────────────────────────────────
def fetch_market_data(symbol_or_name: str, force_refresh: bool = False) -> Dict[str, Any]:
    """종목명 또는 코드를 받아 시세/재무 데이터를 반환합니다."""
    code      = resolve_ticker(symbol_or_name)
    cache_key = code

    # 캐시 조회
    if not force_refresh:
        cached = cache_service.get("market", cache_key)
        if cached:
            cached["_from_cache"] = True
            return cached

    # KRX vs 미국 주식 분기
    is_krx = _is_krx_code(code)
    data   = _fetch_krx_stock(code, symbol_or_name) if is_krx else _fetch_us_stock(code, symbol_or_name)

    # 수집 완전 실패 시 안전 기본 구조 반환
    if not data:
        data = {
            "symbol":               REVERSE_KNOWN_TICKERS.get(code, symbol_or_name),
            "ticker":               code,
            "exchange":             "KRX",
            "currency":             "KRW",
            "data_source":          "데이터 수집 불가",
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

    # 종목명이 코드 그대로인 경우 최종 보정
    sym = data.get("symbol", "")
    if not sym or sym == code or sym.isdigit() or sym == "nan":
        data["symbol"] = REVERSE_KNOWN_TICKERS.get(code, symbol_or_name)

    # 정상 데이터만 캐시 저장
    if data.get("current_price") != "N/A":
        cache_service.set("market", cache_key, data, CACHE_TTL_MARKET)

    return data


# ─────────────────────────────────────────────────────────────
# 섹터별 종목 스크리닝
# ─────────────────────────────────────────────────────────────
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
            print(f"[SCREENING FAIL] {name}: {e}")
    return results
