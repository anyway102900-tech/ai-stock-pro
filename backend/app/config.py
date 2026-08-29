import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DART_API_KEY = os.getenv("DART_API_KEY", "")
KIWOOM_APP_KEY = os.getenv("KIWOOM_APP_KEY", "")
KIWOOM_APP_SECRET = os.getenv("KIWOOM_APP_SECRET", "")
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")

# 캐시 만료 시간 (초 단위)
CACHE_TTL_MARKET = int(os.getenv("CACHE_TTL_MARKET", 900))       # 15분
CACHE_TTL_NEWS = int(os.getenv("CACHE_TTL_NEWS", 7200))           # 2시간
CACHE_TTL_FINANCIAL = int(os.getenv("CACHE_TTL_FINANCIAL", 86400)) # 24시간

# 화이트리스트 언론사 목록
WHITELIST_NEWS_SOURCES = [
    "한국경제",
    "한국경제TV",
    "연합인포맥스",
    "매일경제",
    "머니투데이",
    "이데일리",
    "서울경제",
    "조선비즈",
    "블룸버그",
    "로이터"
]
