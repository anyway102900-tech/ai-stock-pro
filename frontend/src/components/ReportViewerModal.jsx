import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { 
  X, 
  Printer, 
  Download, 
  Copy, 
  Check, 
  Trash2, 
  ExternalLink,
  Calendar,
  DollarSign,
  TrendingUp,
  ShieldCheck
} from 'lucide-react';

export default function ReportViewerModal({ report, onClose, onDelete }) {
  const [copied, setCopied] = useState(false);

  if (!report) return null;

  const meta = report.meta || {};
  const content = report.content || '';

  // 클립보드 복사
  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // .md 파일 직접 다운로드
  const handleDownload = () => {
    const filename = meta.filename || `${meta.symbol || '종목분석'}_리포트.md`;
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // 브라우저 PDF 인쇄
  const handlePrintPdf = () => {
    window.print();
  };

  // 투자 등급 뱃지 스타일
  const getVerdictBadge = (verdict) => {
    if (!verdict) return null;
    if (verdict.includes('적극') || verdict.includes('Strong')) {
      return <span className="badge-verdict badge-strong-buy">🟢 적극 매수</span>;
    }
    if (verdict.includes('분할') || verdict.includes('Buy')) {
      return <span className="badge-verdict badge-buy">🔵 분할 매수</span>;
    }
    if (verdict.includes('주의') || verdict.includes('부적합') || verdict.includes('Unsuitable')) {
      return <span className="badge-verdict badge-unsuitable">🔴 투자 부적합 / 주의</span>;
    }
    return <span className="badge-verdict badge-neutral">🟡 중립 / 관망</span>;
  };

  // 마크다운 표 및 줄바꿈 보정
  const formatReportMarkdown = (text) => {
    if (!text) return '';
    let formatted = text;
    for (let i = 0; i < 15; i++) {
      const prev = formatted;
      formatted = formatted.replace(/\|\s*\|/g, '|\n|');
      if (formatted === prev) break;
    }
    formatted = formatted.replace(/(\|\s*)(:---[-:]*\|)/g, '$1\n$2');
    formatted = formatted.replace(/(:---[-:]*\|)\s*(\|)/g, '$1\n$2');
    formatted = formatted.replace(/(\|)\s*(\d{4}년|\*\*1단계|\*\*2단계|\*\*3단계|\*\*결과|\*\*현재가|\*\*52주|\*\*시가총액|\*\*PER|\*\*배당|\*\*외국인)/g, '$1\n| $2');
    formatted = formatted.replace(/([^\n])(\n?>\s*[📌🔬🛡️])/g, '$1\n\n$2');
    return formatted;
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-container print-area" onClick={(e) => e.stopPropagation()}>
        {/* 모달 상단 헤더 */}
        <div className="modal-header no-print">
          <div className="modal-header-info">
            <div className="modal-title-row">
              <h2 className="modal-title">
                {meta.symbol || '종목 분석 리포트'}
                {meta.ticker && <span className="modal-ticker">({meta.ticker})</span>}
              </h2>
              {getVerdictBadge(meta.verdict)}
            </div>
            <div className="modal-meta-row">
              <span className="modal-meta-item"><Calendar size={13} /> {meta.created_at || '최근'}</span>
              {meta.price && meta.price !== 'N/A' && (
                <span className="modal-meta-item"><DollarSign size={13} /> {meta.price}</span>
              )}
              {meta.per && meta.per !== 'N/A' && (
                <span className="modal-meta-item"><TrendingUp size={13} /> PER {meta.per}</span>
              )}
              {meta.pbr && meta.pbr !== 'N/A' && (
                <span className="modal-meta-item">PBR {meta.pbr}</span>
              )}
            </div>
          </div>

          {/* 액션 버튼 바 */}
          <div className="modal-actions">
            <button className="action-btn action-btn-pdf" onClick={handlePrintPdf} title="PDF로 저장 / 인쇄">
              <Printer size={15} />
              <span>PDF 내보내기</span>
            </button>
            <button className="action-btn" onClick={handleDownload} title=".md 마크다운 파일 다운로드">
              <Download size={15} />
              <span>.md 다운로드</span>
            </button>
            <button className="action-btn" onClick={handleCopy} title="본문 클립보드 복사">
              {copied ? <Check size={15} color="var(--accent-green)" /> : <Copy size={15} />}
              <span>{copied ? '복사됨' : '복사'}</span>
            </button>
            {onDelete && (
              <button 
                className="action-btn action-btn-danger" 
                onClick={() => {
                  if (window.confirm(`'${meta.symbol}' 리포트를 보관함에서 삭제하시겠습니까?`)) {
                    onDelete(meta.filename);
                    onClose();
                  }
                }} 
                title="리포트 삭제"
              >
                <Trash2 size={15} />
              </button>
            )}
            <button className="modal-close-btn" onClick={onClose}>
              <X size={20} />
            </button>
          </div>
        </div>

        {/* 인쇄 전용 헤더 */}
        <div className="print-only-header">
          <h1>AI 주식분석 PRO 팩트체크 리포트 - {meta.symbol} ({meta.ticker})</h1>
          <p>분석 일시: {meta.created_at} | 최종 평가: {meta.verdict} | 현재가: {meta.price} | PER: {meta.per} | PBR: {meta.pbr}</p>
          <hr />
        </div>

        {/* 리포트 마크다운 본문 */}
        <div className="modal-body">
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
            {formatReportMarkdown(content)}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
