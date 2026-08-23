import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { FileCheck, ExternalLink, ShieldCheck, AlertTriangle } from 'lucide-react';

export default function ReportViewer({ report, sources = [], isAnalyzing }) {
  // 프론트엔드 자체 마크다운 테이블 및 줄바꿈 보정
  const formatReportMarkdown = (text) => {
    if (!text) return '';
    let formatted = text;
    // 파이프로 연속된 셀 사이 줄바꿈 복원
    for (let i = 0; i < 15; i++) {
      const prev = formatted;
      formatted = formatted.replace(/\|\s*\|/g, '|\n|');
      if (formatted === prev) break;
    }
    // 구분선 및 행 앞 줄바꿈 보정
    formatted = formatted.replace(/(\|\s*)(:---[-:]*\|)/g, '$1\n$2');
    formatted = formatted.replace(/(:---[-:]*\|)\s*(\|)/g, '$1\n$2');
    formatted = formatted.replace(/(\|)\s*(\d{4}년|\*\*1단계|\*\*2단계|\*\*3단계|\*\*결과|\*\*현재가|\*\*52주|\*\*시가총액|\*\*PER|\*\*배당|\*\*외국인)/g, '$1\n| $2');
    formatted = formatted.replace(/([^\n])(\n?>\s*[📌🔬🛡️])/g, '$1\n\n$2');
    return formatted;
  };

  const processedReport = report ? formatReportMarkdown(report) : null;
  return (
    <section className="glass-card">
      <div className="card-header-bar">
        <div className="card-title">
          <FileCheck size={18} />
          <span>팩트체크 최종 분석 리포트 (Verified Investment Report)</span>
        </div>
        <div>
          {report && (
            <span className="badge-verified">
              ✓ 1차 출처 팩트 검증 완료
            </span>
          )}
        </div>
      </div>

      <div className="report-content">
        {isAnalyzing && !report && (
          <div style={{ padding: '20px 0' }}>
            <div className="skeleton-line" style={{ width: '45%' }}></div>
            <div className="skeleton-line" style={{ width: '80%' }}></div>
            <div className="skeleton-line" style={{ width: '70%' }}></div>
            <div className="skeleton-line" style={{ width: '90%' }}></div>
          </div>
        )}

        {!isAnalyzing && !report && (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}>
            상단에 RICE 프롬프트를 입력하고 분석을 실행하면 공신력 있는 팩트 데이터 기반 최종 리포트가 렌더링됩니다.
          </div>
        )}

        {processedReport && (
          <>
            <ReactMarkdown 
              remarkPlugins={[remarkGfm]}
              components={{
                table: ({ node, ...props }) => (
                  <div className="table-responsive">
                    <table {...props} />
                  </div>
                ),
                a: ({ node, ...props }) => (
                  <a {...props} target="_blank" rel="noopener noreferrer">
                    {props.children} <ExternalLink size={12} style={{ display: 'inline', verticalAlign: 'middle' }} />
                  </a>
                )
              }}
            >
              {processedReport}
            </ReactMarkdown>

            {/* 1차 출처 증빙 섹션 */}
            {sources && sources.length > 0 && (
              <div className="source-box">
                <div className="source-title">
                  <ShieldCheck size={16} />
                  <span>조회된 1차 공식 데이터 출처 (Ground Truth Sources)</span>
                </div>
                {sources.map((src, i) => (
                  <div key={i} className="source-item">
                    <span style={{ color: 'var(--accent-cyan)' }}>• [{src.category}]</span>
                    <span>{src.title}</span>
                    {src.url && (
                      <a href={src.url} target="_blank" rel="noopener noreferrer" style={{ marginLeft: '6px' }}>
                        [원문보기]
                      </a>
                    )}
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.76rem', marginLeft: 'auto' }}>
                      {src.timestamp}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
