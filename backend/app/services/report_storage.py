import os
import re
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

REPORTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "reports"))
os.makedirs(REPORTS_DIR, exist_ok=True)

try:
    from ..tools.market_data import KNOWN_TICKERS
    REVERSE_TICKERS = {v: k for k, v in KNOWN_TICKERS.items()}
except Exception:
    REVERSE_TICKERS = {}

def parse_report_verdict(content: str) -> str:
    if "적극 매수" in content or "Strong Buy" in content:
        return "적극매수"
    elif "분할 매수" in content or "Buy" in content:
        return "분할매수"
    elif "투자 부적합" in content or "Unsuitable" in content:
        return "투자주의"
    elif "중립" in content or "Neutral" in content:
        return "중립"
    return "분석완료"

def extract_metadata_from_content(content: str) -> Dict[str, Any]:
    meta = {
        "symbol": "종목",
        "ticker": "",
        "verdict": parse_report_verdict(content),
        "price": "N/A",
        "market_cap": "N/A",
        "per": "N/A",
        "pbr": "N/A",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # 1. Frontmatter 주석 파싱 (<!-- META: {...} -->)
    meta_match = re.search(r"<!-- META:\s*(\{.*?\})\s*-->", content, re.DOTALL)
    if meta_match:
        try:
            parsed = json.loads(meta_match.group(1))
            meta.update(parsed)
            # 만약 parsed의 symbol이 '종목분석'이거나 숫자인 경우 아래 정밀 추출로 보정
            if meta["symbol"] not in ["종목", "종목분석"] and not meta["symbol"].isdigit():
                return meta
        except Exception:
            pass

    # 2. 리포트 대제목에서 종목명/코드 정밀 추출: 📋 [SAMG엔터 (419530)] or 📋 [419530]
    title_match = re.search(r"📋\s*\[\s*([^(\]\s\n]+)(?:\s*\(([^)]+)\))?\s*\]", content)
    if title_match:
        sym = title_match.group(1).strip()
        tick = title_match.group(2).strip() if title_match.group(2) else ""
        if sym.isdigit() and sym in REVERSE_TICKERS:
            tick = sym
            sym = REVERSE_TICKERS[sym]
        meta["symbol"] = sym
        if tick:
            meta["ticker"] = tick

    # 3. 본문 텍스트 내 종목명 필드 탐색 폴백
    if meta["symbol"] in ["종목", "종목분석"] or meta["symbol"].isdigit():
        symbol_match = re.search(r"(?:종목명|기업명)(?:/코드)?[:\s*|]+([가-힣A-Za-z0-9]+)(?:\s*\(([^)]+)\))?", content)
        if symbol_match:
            s = symbol_match.group(1).strip()
            if s.isdigit() and s in REVERSE_TICKERS:
                meta["ticker"] = s
                meta["symbol"] = REVERSE_TICKERS[s]
            elif s not in ["종목", "종목분석"]:
                meta["symbol"] = s
                if symbol_match.group(2):
                    meta["ticker"] = symbol_match.group(2).strip()

    # 4. 가격 추출
    price_match = re.search(r"\|\s*\*\*현재가\*\*\s*\|\s*([0-9,]+원?)", content)
    if not price_match:
        price_match = re.search(r"(?:현재가|실시간\s*체결가)[^0-9\n]*([0-9,]+원)", content)
    if price_match:
        p_val = price_match.group(1).strip()
        meta["price"] = p_val if p_val.endswith("원") else f"{p_val}원"

    # 5. PER / PBR 추출
    per_pbr_match = re.search(r"\|\s*\*\*PER\s*/\s*PBR\*\*\s*\|\s*([0-9.]+배?)\s*/\s*([0-9.]+배?)", content)
    if per_pbr_match:
        p_per = per_pbr_match.group(1).strip()
        p_pbr = per_pbr_match.group(2).strip()
        meta["per"] = p_per if "배" in p_per else f"{p_per}배"
        meta["pbr"] = p_pbr if "배" in p_pbr else f"{p_pbr}배"
    else:
        per_match = re.search(r"PER[^0-9\n]*([0-9.]+배)", content)
        if per_match:
            meta["per"] = per_match.group(1)
        pbr_match = re.search(r"PBR[^0-9\n]*([0-9.]+배)", content)
        if pbr_match:
            meta["pbr"] = pbr_match.group(1)

    # 6. 날짜 추출
    date_match = re.search(r"분석\s*기준일자\*\*:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", content)
    if date_match:
        meta["created_at"] = date_match.group(1)

    return meta

def save_markdown_report(symbol: str, content: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    now = datetime.now()
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    display_time = now.strftime("%Y-%m-%d %H:%M:%S")
    
    extracted = extract_metadata_from_content(content)
    
    clean_symbol = symbol or extracted.get("symbol", "종목분석")
    if clean_symbol in ["종목", "종목분석"] and extracted.get("symbol") not in ["종목", "종목분석"]:
        clean_symbol = extracted.get("symbol")
        
    clean_symbol = re.sub(r'[\\/*?:"<>|]', "", clean_symbol).strip()
    verdict = meta.get("verdict") if (meta and meta.get("verdict")) else extracted.get("verdict", "분석완료")
    
    filename = f"{timestamp_str}_{clean_symbol}_{verdict}.md"
    file_path = os.path.join(REPORTS_DIR, filename)
    
    full_meta = {
        "filename": filename,
        "symbol": clean_symbol,
        "ticker": meta.get("ticker") if (meta and meta.get("ticker")) else extracted.get("ticker", ""),
        "verdict": verdict,
        "price": meta.get("price") if (meta and meta.get("price") != "N/A") else extracted.get("price", "N/A"),
        "market_cap": meta.get("market_cap") if (meta and meta.get("market_cap") != "N/A") else extracted.get("market_cap", "N/A"),
        "per": meta.get("per") if (meta and meta.get("per") != "N/A") else extracted.get("per", "N/A"),
        "pbr": meta.get("pbr") if (meta and meta.get("pbr") != "N/A") else extracted.get("pbr", "N/A"),
        "created_at": display_time
    }
    
    frontmatter = f"<!-- META: {json.dumps(full_meta, ensure_ascii=False)} -->\n\n"
    final_content = frontmatter + content.lstrip()
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(final_content)
        
    return full_meta

def list_all_reports() -> List[Dict[str, Any]]:
    if not os.path.exists(REPORTS_DIR):
        return []
        
    reports = []
    for fn in os.listdir(REPORTS_DIR):
        if not fn.endswith(".md"):
            continue
        file_path = os.path.join(REPORTS_DIR, fn)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            meta = extract_metadata_from_content(content)
            meta["filename"] = fn
            meta["file_size_bytes"] = os.path.getsize(file_path)
            reports.append(meta)
        except Exception as e:
            print(f"Error reading report {fn}: {e}")
            
    reports.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return reports

def get_report_content(filename: str) -> Optional[Dict[str, Any]]:
    safe_name = os.path.basename(filename)
    file_path = os.path.join(REPORTS_DIR, safe_name)
    if not os.path.exists(file_path):
        return None
        
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    meta = extract_metadata_from_content(content)
    meta["filename"] = safe_name
    
    clean_content = re.sub(r"<!-- META:.*?-->\n*", "", content, flags=re.DOTALL)
    
    return {
        "meta": meta,
        "content": clean_content.strip()
    }

def delete_report_file(filename: str) -> bool:
    safe_name = os.path.basename(filename)
    file_path = os.path.join(REPORTS_DIR, safe_name)
    if os.path.exists(file_path):
        os.remove(file_path)
        return True
    return False
