import React, { useState } from 'react';
import { Play, Sparkles, RefreshCw, FileText } from 'lucide-react';

export default function PromptInput({ onExecute, isAnalyzing }) {
  const [prompt, setPrompt] = useState(
`[AI 성장주 RICE 분석 요청]
- 종목명: 리노공업 (또는 한미반도체, 엔비디아)
- 요구 조건:
  1. 실시간 주가 및 52주 최고/최저, PER/PBR 시가총액 팩트체크
  2. Open DART 최근 사업보고서 기준 3개년 매출 및 영업이익 CAGR 산출
  3. 한국경제/한국경제TV 등 화이트리스트 언론사 최신 모멘텀 기사 3건 요약
  4. 외부 추측 배제 및 데이터 미존재 시 (N/A) 명시하여 최종 마크다운 표로 정리할 것`
  );
  const [forceRefresh, setForceRefresh] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!prompt.trim() || isAnalyzing) return;
    onExecute(prompt, forceRefresh);
  };

  return (
    <section className="glass-card">
      <div className="card-header-bar">
        <div className="card-title">
          <FileText size={18} />
          <span>RICE 프롬프트 입력</span>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <label className="checkbox-label">
            <input 
              type="checkbox" 
              checked={forceRefresh} 
              onChange={(e) => setForceRefresh(e.target.checked)}
              disabled={isAnalyzing}
            />
            <RefreshCw size={13} style={{ verticalAlign: 'middle' }} />
            <span>캐시 무시 (강제 실시간 갱신)</span>
          </label>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="prompt-input-wrapper">
        <textarea
          className="prompt-textarea"
          rows={6}
          placeholder="목적에 맞게 생성된 RICE 프롬프트(AI 성장주, 고배당주, 턴어라운드주 등)를 여기에 붙여넣으세요..."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          disabled={isAnalyzing}
        />

        <div className="prompt-controls">
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            * Gemini 두뇌가 DART/공인뉴스/시세 Tool을 강제 호출하여 팩트 기반 리포트를 작성합니다.
          </span>
          <button
            type="submit"
            className="btn-primary"
            disabled={isAnalyzing || !prompt.trim()}
          >
            {isAnalyzing ? (
              <>
                <RefreshCw size={16} className="spin-animation" style={{ animation: 'spin 1s linear infinite' }} />
                <span>팩트체크 수행 중...</span>
              </>
            ) : (
              <>
                <Play size={16} fill="currentColor" />
                <span>분석 실행</span>
              </>
            )}
          </button>
        </div>
      </form>
    </section>
  );
}
