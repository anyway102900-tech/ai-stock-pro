# AI 주식분석 PRO 팩트체크 에이전트 대시보드

공신력 있는 1차 데이터(DART 전자공시, 네이버 화이트리스트 뉴스, yfinance/pykrx 실시간 시세)만을 강제로 탐색하여 환각(Hallucination) 없는 전문 투자 리포트를 생성하는 대시보드 시스템입니다.

---

## 🚀 빠른 시작 가이드

### 1. 백엔드 실행 (FastAPI)
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. 프론트엔드 실행 (React / Vite)
```bash
cd frontend
npm install
npm run dev
```
- 브라우저 접속: `http://localhost:5173`

---

## 🛠️ 주요 기능
1. **RICE 프롬프트 파싱 및 실행:** 사용자가 목적에 맞게 작성한 RICE 프롬프트를 입력하면 종목 및 지표 요구조건을 자동 식별
2. **실시간 시세 & 밸류에이션 팩트체크:** yfinance 및 한국거래소 기준 실시간 현재가, 52주 최고/최저, PER, PBR, 시가총액 산출
3. **Open DART 전자공시 3개년 CAGR:** 정기 사업보고서 기반 매출액 및 영업이익의 3개년 복합 연간 성장률(CAGR) 계산
4. **공인 화이트리스트 뉴스 필터링:** 한국경제, 한국경제TV, 연합인포맥스 등 공인 언론사 기사만 추출하고 루머 배제
5. **Multi-Tier 캐싱 시스템:** 시세(15분), 뉴스(2시간), 재무공시(24시간) 로컬 캐싱 및 [캐시 무시] 강제 갱신 지원
6. **Hallucination-Zero 가드레일:** 1차 데이터가 없는 항목은 임의 추측 없이 `(N/A)` 명시 및 1차 출처 증빙 URL 자동 첨부
