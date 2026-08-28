import os
import re
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

REPORTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "reports"))
os.makedirs(REPORTS_DIR, exist_ok=True)

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
    
    # Frontmatter 주석 파싱 (<!-- META: {...} -->)
    meta_match = re.search(r"<!-- META:\s*(\{.*?\})\s*-->", content, re.DOTALL)
    if meta_match:
        try:
            parsed = json.loads(meta_match.group(1))
            meta.update(parsed)
            return meta
        except Exception:
            pass

    # 본문 텍스트 기반 추출 폴백
    symbol_match = re.search(r"종목명(?:/코드)?:\s*([^\s(]+)(?:\s*\(([^)]+)\))?", content)
    if symbol_match:
        meta["symbol"] = symbol_match.group(1)
        if symbol_match.group(2):
            meta["ticker"] = symbol_match.group(2)
            
    price_match = re.search(r"현재가:\s*([0-9,]+원)", content)
    if price_match:
        meta["price"] = price_match.group(1)
        
    per_match = re.search(r"PER:\s*([0-9.]+배|N/A)", content)
    if per_match:
        meta["per"] = per_match.group(1)
        
    pbr_match = re.search(r"PBR:\s*([0-9.]+배|N/A)", content)
    if pbr_match:
        meta["pbr"] = pbr_match.group(1)

    return meta

def save_markdown_report(symbol: str, content: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    now = datetime.now()
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    display_time = now.strftime("%Y-%m-%d %H:%M:%S")
    
    clean_symbol = re.sub(r'[\\/*?:"<>|]', "", symbol or "종목분석").strip()
    verdict = meta.get("verdict") if meta else parse_report_verdict(content)
    
    filename = f"{timestamp_str}_{clean_symbol}_{verdict}.md"
    file_path = os.path.join(REPORTS_DIR, filename)
    
    # 메타데이터 병합
    full_meta = {
        "filename": filename,
        "symbol": clean_symbol,
        "ticker": meta.get("ticker", "") if meta else "",
        "verdict": verdict,
        "price": meta.get("price", "N/A") if meta else "N/A",
        "market_cap": meta.get("market_cap", "N/A") if meta else "N/A",
        "per": meta.get("per", "N/A") if meta else "N/A",
        "pbr": meta.get("pbr", "N/A") if meta else "N/A",
        "created_at": display_time
    }
    
    # 마크다운 상단에 메타데이터 주석 삽입
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
                header = f.read(1500)
            meta = extract_metadata_from_content(header)
            meta["filename"] = fn
            meta["file_size_bytes"] = os.path.getsize(file_path)
            reports.append(meta)
        except Exception as e:
            print(f"Error reading report {fn}: {e}")
            
    # 생성일시 내림차순 정렬 (최신순)
    reports.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return reports

def get_report_content(filename: str) -> Optional[Dict[str, Any]]:
    # 보안: 디렉터리 경로 트래버설 방지
    safe_name = os.path.basename(filename)
    file_path = os.path.join(REPORTS_DIR, safe_name)
    if not os.path.exists(file_path):
        return None
        
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    meta = extract_metadata_from_content(content)
    meta["filename"] = safe_name
    
    # 메타 주석 제거한 본문
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
