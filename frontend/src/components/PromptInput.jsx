import React, { useState, useEffect, useRef } from 'react';
import { Play, RefreshCw, Search, CheckCircle2, TrendingUp } from 'lucide-react';
import krxStocks from '../krx_stocks.json';

const QUICK_STOCKS = [
  { name: '클래시스', code: '214150', desc: '의료기기/슈링크' },
  { name: '리브스메드', code: '491000', desc: '의료로봇/신규상장' },
  { name: 'SAMG엔터', code: '419530', desc: '티니핑 IP/턴어라운드' },
  { name: '디케이티', code: '290550', desc: '스마트폰/전자부품' },
  { name: '케어젠', code: '214370', desc: '바이오 펩타이드' },
  { name: '삼성전자', code: '005930', desc: '반도체/AI' },
  { name: '두산에너빌리티', code: '034020', desc: '원전/전력망' },
];

export default function PromptInput({ onExecute, isAnalyzing }) {
  const [prompt, setPrompt] = useState('클래시스 (214150)');
  const [forceRefresh, setForceRefresh] = useState(true);
  const [suggestions, setSuggestions] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef(null);

  // 실시간 종목명 및 종목코드 자동완성 필터링
  useEffect(() => {
    const trimmed = prompt.trim();
    if (!trimmed || trimmed.includes('\n') || trimmed.length > 30) {
      setSuggestions([]);
      return;
    }

    // 괄호가 이미 들어있는 경우(예: '클래시스 (214150)')는 자동완성 숨김
    if (trimmed.includes('(') && trimmed.includes(')')) {
      setSuggestions([]);
      return;
    }

    const query = trimmed.toLowerCase();
    const matches = [];
    const seen = new Set();

    // 1. krx_stocks.json 매칭
    for (const [name, code] of Object.entries(krxStocks)) {
      if (name.toLowerCase().includes(query) || code.includes(query)) {
        if (!seen.has(code)) {
          seen.add(code);
          matches.push({ name, code });
          if (matches.length >= 8) break;
        }
      }
    }

    setSuggestions(matches);
  }, [prompt]);

  // 바깥 클릭 시 드롭다운 닫기
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!prompt.trim() || isAnalyzing) return;
    setShowDropdown(false);
    onExecute(prompt, forceRefresh);
  };

  const handleSelectStock = (stock) => {
    setPrompt(`${stock.name} (${stock.code})`);
    setSuggestions([]);
    setShowDropdown(false);
  };

  return (
    <section className="glass-card" style={{ position: 'relative' }}>
      <div className="card-header-bar">
        <div className="card-title">
          <Search size={18} />
          <span>종목명 검색 (종목번호 자동완성)</span>
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
          인기 종목:
        </span>
        {QUICK_STOCKS.map((s) => (
          <button
            key={s.name}
            type="button"
            className="chip-btn"
            style={{
              background: prompt.includes(s.name) ? 'rgba(59, 130, 246, 0.25)' : 'rgba(255, 255, 255, 0.05)',
              border: prompt.includes(s.name) ? '1px solid #3b82f6' : '1px solid rgba(255, 255, 255, 0.1)',
              color: prompt.includes(s.name) ? '#60a5fa' : 'var(--text-color)',
              padding: '4px 10px',
              borderRadius: '16px',
              fontSize: '0.8rem',
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
            onClick={() => handleSelectStock(s)}
            disabled={isAnalyzing}
          >
            <strong>{s.name}</strong> <span style={{ color: '#38bdf8', fontSize: '0.75rem', marginLeft: '3px' }}>[{s.code}]</span>
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="prompt-input-wrapper" style={{ position: 'relative' }} ref={dropdownRef}>
        <div style={{ position: 'relative', width: '100%' }}>
          <textarea
            className="prompt-textarea"
            rows={2}
            placeholder="종목명(예: 클래시스, 리브스메드, SAMG, 디케이티) 또는 코드를 입력하면 종목번호가 자동완성됩니다..."
            value={prompt}
            onChange={(e) => {
              setPrompt(e.target.value);
              setShowDropdown(true);
            }}
            onFocus={() => setShowDropdown(true)}
            disabled={isAnalyzing}
            style={{ fontSize: '0.95rem', paddingRight: '40px' }}
          />

          {/* 🔍 실시간 종목번호 자동완성 드롭다운 */}
          {showDropdown && suggestions.length > 0 && (
            <div
              style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                right: 0,
                background: 'rgba(15, 23, 42, 0.96)',
                backdropFilter: 'blur(16px)',
                border: '1px solid rgba(59, 130, 246, 0.4)',
                borderRadius: '10px',
                marginTop: '4px',
                zIndex: 999,
                boxShadow: '0 12px 30px rgba(0, 0, 0, 0.6)',
                overflow: 'hidden',
              }}
            >
              <div style={{ padding: '8px 12px', fontSize: '0.75rem', color: '#94a3b8', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                ⚡ 실시간 KRX 공식 상장 종목 자동완성 (클릭 시 자동 선택)
              </div>
              {suggestions.map((item, idx) => (
                <div
                  key={item.code + idx}
                  onClick={() => handleSelectStock(item)}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '10px 14px',
                    cursor: 'pointer',
                    borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(59, 130, 246, 0.2)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <TrendingUp size={14} color="#60a5fa" />
                    <span style={{ fontWeight: '600', color: '#f8fafc', fontSize: '0.9rem' }}>{item.name}</span>
                  </div>
                  <span
                    style={{
                      background: 'rgba(59, 130, 246, 0.2)',
                      color: '#38bdf8',
                      padding: '2px 8px',
                      borderRadius: '6px',
                      fontSize: '0.8rem',
                      fontWeight: 'bold',
                      fontFamily: 'monospace',
                      border: '1px solid rgba(56, 189, 248, 0.3)',
                    }}
                  >
                    {item.code}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="prompt-controls" style={{ marginTop: '8px' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            * 종목명을 입력하면 6자리 공식 코드가 자동 매핑되어 한국거래소, DART, FnGuide에서 100% 팩트 수집을 진행합니다.
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
