import React from 'react';
import { ShieldCheck, Activity, Cpu, Database } from 'lucide-react';

export default function Header({ status = 'ready' }) {
  return (
    <header className="dashboard-header">
      <div className="brand-section">
        <div className="brand-icon-wrapper">
          <ShieldCheck size={26} />
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '6px' }}>
            <h1 className="brand-title">AI 주식분석 PRO</h1>
            <span className="brand-badge">FACT-CHECK AGENT</span>
          </div>
          <p className="brand-subtitle">공신력 있는 1차 데이터(DART, 공인 뉴스, 시세) 기반 노이즈 0% 투자 검증 시스템</p>
        </div>
      </div>

      <div className="header-status-panel">
        <div className="status-chip">
          <Database size={14} color="#00f2fe" />
          <span>Multi-Tier Cache: <strong>ON</strong></span>
        </div>
        <div className="status-chip">
          <Cpu size={14} color="#a855f7" />
          <span>LLM: <strong>Gemini 1.5</strong></span>
        </div>
        <div className="status-chip">
          <span className="pulse-dot" style={{ backgroundColor: status === 'analyzing' ? '#f59e0b' : '#10b981' }}></span>
          <span>{status === 'analyzing' ? '에이전트 탐색 중' : '시스템 준비 완료'}</span>
        </div>
      </div>
    </header>
  );
}
