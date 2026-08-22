import sys
import requests
import json

# UTF-8 출력 강제 설정
sys.stdout.reconfigure(encoding='utf-8')

url = "http://127.0.0.1:8000/api/analyze"
payload = {
    "prompt": """🏆 AI 성장주 발굴
R (Role) - 역할: 20년 경력의 AI 섹터 전문 애널리스트
I (Instruction) - 지시사항: 다음 조건에 맞는 5개를 발굴해주세요:
스크리닝 조건: AI 섹터, PEG 1.5 이하, 매출 CAGR 15%+
E (Example) - 출력 형식
🏆 AI 성장주 TOP 5개
1순위: [종목명] - [핵심 투자포인트 한 줄]
📊 종합 비교표
🎯 최종 추천""",
    "force_refresh": True
}

print("=== 백엔드 실시간 구글 검색 파이프라인 테스트 ===")
try:
    resp = requests.post(url, json=payload, stream=True, timeout=90)
    for line in resp.iter_lines():
        if line:
            decoded = line.decode('utf-8')
            if decoded.startswith('data: '):
                data = json.loads(decoded[6:])
                if data.get('type') == 'log':
                    print(f"[{data.get('tag')}] {data.get('message')}")
                elif data.get('type') == 'result':
                    print("\n=======================================================")
                    print("🎉 [성공] 최종 실시간 팩트체크 리포트 수신 완료!")
                    print("=======================================================\n")
                    print(data.get('report')[:600])
                    print("\n... [생략] ...\n")
                    print("=== 1차 출처 목록 ===")
                    for s in data.get('sources', []):
                        print(f"- [{s.get('category')}] {s.get('title')}")
except Exception as e:
    print("테스트 에러:", e)
