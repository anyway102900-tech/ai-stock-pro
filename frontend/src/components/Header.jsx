import React from 'react';
import { ShieldCheck, Cpu, Database, BarChart3, FolderArchive } from 'lucide-react';

export default function Header({ status = 'ready', activeTab = 'analyze', onTabChange, reportCount = 0 }) {
  return (
    <header className="dashboard-header">
      <div className="header-top-row">
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
            <span>LLM: <strong>Gemini 2.5 / 1.5</strong></span>
          </div>
          <div className="status-chip">
            <span className="pulse-dot" style={{ backgroundColor: status === 'analyzing' ? '#f59e0b' : '#10b981' }}></span>
            <span>{status === 'analyzing' ? '에이전트 탐색 중' : '시스템 준비 완료'}</span>
          </div>
        </div>
      </div>

      {/* 네비게이션 탭 바 */}
      <nav className="header-nav-tabs">
        <button 
          className={`nav-tab-btn ${activeTab === 'analyze' ? 'active' : ''}`}
          onClick={() => onTabChange && onTabChange('analyze')}
        >
          <BarChart3 size={16} />
          <span>실시간 AI 분석</span>
        </button>
        <button 
          className={`nav-tab-btn ${activeTab === 'archive' ? 'active' : ''}`}
          onClick={() => onTabChange && onTabChange('archive')}
        >
          <FolderArchive size={16} />
          <span>리포트 보관함 (.md)</span>
          {reportCount > 0 && <span className="nav-tab-badge">{reportCount}</span>}
        </button>
      </nav>
    </header>
  );
}
