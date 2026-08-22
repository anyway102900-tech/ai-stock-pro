import React, { useState } from 'react';
import { Play, Sparkles, RefreshCw, FileText, Search } from 'lucide-react';

const QUICK_STOCKS = [
  { name: 'SAMG엔터', desc: '티니핑 IP/턴어라운드' },
  { name: '디케이티', desc: '스마트폰/전자부품' },
  { name: '케어젠', desc: '바이오 펩타이드' },
  { name: '두산에너빌리티', desc: '원전/전력망' },
  { name: '삼성전자', desc: '반도체/AI' },
  { name: 'KODEX 방산TOP10', desc: 'K-방산 대표 ETF' },
];

export default function PromptInput({ onExecute, isAnalyzing }) {
  const [prompt, setPrompt] = useState('SAMG엔터');
  const [forceRefresh, setForceRefresh] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!prompt.trim() || isAnalyzing) return;
    onExecute(prompt, forceRefresh);
  };

  const handleSelectQuickStock = (stockName) => {
    setPrompt(stockName);
  };

  return (
    <section className="glass-card">
      <div className="card-header-bar">
        <div className="card-title">
          <Search size={18} />
          <span>종목명 또는 RICE 프롬프트 입력</span>
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

      {/* 빠른 종목 원클릭 칩 */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '14px' }}>
        <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)', alignSelf: 'center', marginRight: '4px' }}>
          빠른 선택:
        </span>
        {QUICK_STOCKS.map((s) => (
          <button
            key={s.name}
            type="button"
            className="chip-btn"
            style={{
              background: prompt === s.name ? 'rgba(59, 130, 246, 0.25)' : 'rgba(255, 255, 255, 0.05)',
              border: prompt === s.name ? '1px solid #3b82f6' : '1px solid rgba(255, 255, 255, 0.1)',
              color: prompt === s.name ? '#60a5fa' : 'var(--text-color)',
              padding: '4px 10px',
              borderRadius: '16px',
              fontSize: '0.8rem',
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
            onClick={() => handleSelectQuickStock(s.name)}
            disabled={isAnalyzing}
          >
            <strong>{s.name}</strong> <span style={{ opacity: 0.7, fontSize: '0.75rem' }}>({s.desc})</span>
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="prompt-input-wrapper">
        <textarea
          className="prompt-textarea"
          rows={3}
          placeholder="종목명(예: SAMG엔터, 디케이티, 005930)만 입력하거나 맞춤형 RICE 프롬프트를 입력하세요..."
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          disabled={isAnalyzing}
        />

        <div className="prompt-controls">
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            * 종목명만 입력해도 한국거래소(KRX), DART 전자공시, FnGuide, 공인뉴스에서 실시간 팩트체크 리포트를 자동 작성합니다.
          </span>
          <button
            type="submit"
            className="btn-primary"
            disabled={isAnalyzing || !prompt.trim()}
          >
            {isAnalyzing ? (
              <>
                <RefreshCw size={16} className="spin-animation" style={{ animation: 'spin 1s linear infinite' }} />
                <span>공식 매체 실시간 수집 및 분석 중...</span>
              </>
            ) : (
              <>
                <Play size={16} fill="currentColor" />
                <span>공식 매체 실시간 분석</span>
              </>
            )}
          </button>
        </div>
      </form>
    </section>
  );
}
