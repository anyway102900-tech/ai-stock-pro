import React, { useEffect, useRef } from 'react';
import { Terminal, CheckCircle2, AlertCircle } from 'lucide-react';

export default function ExecutionConsole({ logs = [], isAnalyzing }) {
  const consoleBottomRef = useRef(null);

  useEffect(() => {
    consoleBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <section className="glass-card">
      <div className="card-header-bar">
        <div className="card-title">
          <Terminal size={18} />
          <span>에이전트 실시간 작업 콘솔 (Fact-Check Stream)</span>
        </div>
        <div>
          {isAnalyzing && (
            <span style={{ fontSize: '0.78rem', color: 'var(--accent-amber)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span className="pulse-dot" style={{ backgroundColor: '#f59e0b', width: '6px', height: '6px' }}></span>
              도구 호출 및 가드레일 검증 진행 중
            </span>
          )}
        </div>
      </div>

      <div className="console-body">
        {logs.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', textAlign: 'center', margin: 'auto' }}>
            프롬프트를 입력하고 [분석 실행]을 누르면 에이전트의 실시간 팩트 수집 및 추론 로그가 여기에 스트리밍됩니다.
          </div>
        ) : (
          logs.map((log, index) => (
            <div key={index} className="log-entry">
              <span className="log-timestamp">{log.time}</span>
              <span className={`log-tag ${log.type}`}>{log.tag || log.type}</span>
              <span className="log-message">{log.message}</span>
            </div>
          ))
        )}
        <div ref={consoleBottomRef} />
      </div>
    </section>
  );
}
