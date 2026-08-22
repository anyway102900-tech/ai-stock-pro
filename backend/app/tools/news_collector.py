import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from urllib.parse import quote_plus
from datetime import datetime
from ..config import WHITELIST_NEWS_SOURCES, CACHE_TTL_NEWS
from ..services.cache_service import cache_service

def fetch_whitelist_news(keyword: str, max_articles: int = 4, force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    네이버 뉴스 검색을 통해 화이트리스트 공인 언론사 기사만을 엄격하게 수집합니다.
    """
    cache_key = f"news_{keyword}"

    if not force_refresh:
        cached = cache_service.get("news", cache_key)
        if cached:
            return cached

    articles = []
    try:
        encoded_query = quote_plus(f"{keyword} 주가 전망 실적")
        url = f"https://search.naver.com/search.naver?where=news&query={encoded_query}&sort=1" # 최신순
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            news_items = soup.select(".news_wrap")

            for item in news_items:
                press_elem = item.select_one(".info_group .press")
                press = press_elem.text.replace("언론사 선정", "").strip() if press_elem else ""

                # 화이트리스트 언론사인지 엄격 검증
                is_whitelisted = any(w_source in press for w_source in WHITELIST_NEWS_SOURCES)
                if not is_whitelisted:
                    continue

                title_elem = item.select_one(".news_tit")
                if not title_elem:
                    continue

                title = title_elem.text.strip()
                link = title_elem.get("href", "")
                
                desc_elem = item.select_one(".dsc_wrap")
                desc = desc_elem.text.strip() if desc_elem else ""

                time_elem = item.select_one(".info_group span.info")
                pub_time = time_elem.text.strip() if time_elem else datetime.now().strftime("%Y-%m-%d")

                articles.append({
                    "press": press,
                    "title": title,
                    "url": link,
                    "summary": desc,
                    "published_at": pub_time,
                    "verified": True
                })

                if len(articles) >= max_articles:
                    break

        # 수집된 기사가 없을 경우 기본 안내 기사 또는 N/A 처리
        if not articles:
            articles.append({
                "press": "시스템 필터",
                "title": f"최근 수집된 공인 화이트리스트 언론사 기사 없음 (N/A)",
                "url": "",
                "summary": "신뢰할 수 있는 1차 언론사 기사가 없어 자의적 해석을 배제합니다.",
                "published_at": datetime.now().strftime("%Y-%m-%d"),
                "verified": False
            })

        cache_service.set("news", cache_key, articles, CACHE_TTL_NEWS)
        return articles

    except Exception as e:
        return [{
            "press": "오류",
            "title": f"뉴스 수집 중 일시적 오류: {str(e)}",
            "url": "",
            "summary": "N/A",
            "published_at": datetime.now().strftime("%Y-%m-%d"),
            "verified": False
        }]
