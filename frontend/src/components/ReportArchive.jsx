import React, { useState, useEffect } from 'react';
import { 
  FolderOpen, 
  Search, 
  Trash2, 
  Download, 
  ExternalLink, 
  RefreshCw, 
  Calendar, 
  TrendingUp, 
  DollarSign, 
  FileText,
  Filter
} from 'lucide-react';
import ReportViewerModal from './ReportViewerModal';

export default function ReportArchive({ apiBaseUrl = '' }) {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedVerdict, setSelectedVerdict] = useState('ALL');
  const [activeReportDetail, setActiveReportDetail] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // 리포트 목록 불러오기 (백엔드 API + LocalStorage 병합)
  const fetchReports = async () => {
    setLoading(true);
    let apiReports = [];
    
    try {
      const res = await fetch(`${apiBaseUrl}/api/reports`);
      if (res.ok) {
        const data = await res.json();
        apiReports = data.reports || [];
      }
    } catch (err) {
      console.warn('API 리포트 불러오기 실패, 로컬 캐시 사용:', err);
    }

    // LocalStorage 백업 데이터 병합 (동기화)
    let localReports = [];
    try {
      const saved = localStorage.getItem('ai_stock_saved_reports');
      if (saved) {
        localReports = JSON.parse(saved);
      }
    } catch (e) {
      console.error('LocalStorage 파싱 오류:', e);
    }

    // 파일명 또는 생성일시 기준 중복 제거 병합
    const map = new Map();
    [...apiReports, ...localReports].forEach((r) => {
      const key = r.filename || `${r.symbol}_${r.created_at}`;
      if (!map.has(key)) {
        map.set(key, r);
      }
    });

    const combined = Array.from(map.values()).sort(
      (a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0)
    );

    setReports(combined);
    setLoading(false);
  };

  useEffect(() => {
    fetchReports();
  }, []);

  // 리포트 상세 열람
  const handleOpenReport = async (reportMeta) => {
    try {
      // 1. 백엔드에서 원문 조회 시도
      if (reportMeta.filename) {
        const res = await fetch(`${apiBaseUrl}/api/reports/${encodeURIComponent(reportMeta.filename)}`);
        if (res.ok) {
          const detail = await res.json();
          setActiveReportDetail(detail);
          setIsModalOpen(true);
          return;
        }
      }
    } catch (err) {
      console.warn('백엔드 상세 조회 실패, 로컬 데이터 확인:', err);
    }

    // 2. 백엔드 실패 시 로컬스토리지 본문 확인
    if (reportMeta.content) {
      setActiveReportDetail({
        meta: reportMeta,
        content: reportMeta.content
      });
      setIsModalOpen(true);
    } else {
      alert('리포트 본문을 불러오지 못했습니다.');
    }
  };

  // 리포트 삭제
  const handleDeleteReport = async (filename) => {
    // 1. 백엔드 삭제
    try {
      if (filename) {
        await fetch(`${apiBaseUrl}/api/reports/${encodeURIComponent(filename)}`, {
          method: 'DELETE'
        });
      }
    } catch (err) {
      console.error('백엔드 삭제 오류:', err);
    }

    // 2. LocalStorage 삭제
    try {
      const saved = localStorage.getItem('ai_stock_saved_reports');
      if (saved) {
        const parsed = JSON.parse(saved);
        const filtered = parsed.filter((r) => r.filename !== filename);
        localStorage.setItem('ai_stock_saved_reports', JSON.stringify(filtered));
      }
    } catch (e) {}

    // 상태 업데이트
    setReports((prev) => prev.filter((r) => r.filename !== filename));
  };

  // .md 다운로드
  const handleDownload = (e, reportMeta) => {
    e.stopPropagation();
    if (reportMeta.filename) {
      window.open(`${apiBaseUrl}/api/reports/${encodeURIComponent(reportMeta.filename)}/download`, '_blank');
    }
  };

  // 등급 뱃지
  const getVerdictBadge = (verdict) => {
    if (!verdict) return <span className="badge-verdict badge-neutral">분석완료</span>;
    if (verdict.includes('적극') || verdict.includes('Strong')) {
      return <span className="badge-verdict badge-strong-buy">🟢 적극 매수</span>;
    }
    if (verdict.includes('분할') || verdict.includes('Buy')) {
      return <span className="badge-verdict badge-buy">🔵 분할 매수</span>;
    }
    if (verdict.includes('주의') || verdict.includes('부적합') || verdict.includes('Unsuitable')) {
      return <span className="badge-verdict badge-unsuitable">🔴 투자주의</span>;
    }
    return <span className="badge-verdict badge-neutral">🟡 중립·관망</span>;
  };

  // 검색 및 필터링
  const filteredReports = reports.filter((r) => {
    const symbolMatch = (r.symbol || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
                        (r.ticker || '').toLowerCase().includes(searchQuery.toLowerCase());
    
    if (!symbolMatch) return false;

    if (selectedVerdict === 'ALL') return true;
    if (selectedVerdict === 'STRONG_BUY') return (r.verdict || '').includes('적극');
    if (selectedVerdict === 'BUY') return (r.verdict || '').includes('분할');
    if (selectedVerdict === 'NEUTRAL') return (r.verdict || '').includes('중립');
    if (selectedVerdict === 'UNSUITABLE') return (r.verdict || '').includes('주의') || (r.verdict || '').includes('부적합');
    return true;
  });

  return (
    <div className="archive-container">
      {/* 상단 툴바: 검색, 필터, 새로고침 */}
      <div className="glass-card archive-toolbar">
        <div className="archive-search-box">
          <Search size={16} className="search-icon" />
          <input
            type="text"
            placeholder="저장된 종목명 또는 종목코드 검색..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="archive-search-input"
          />
          {searchQuery && (
            <button className="clear-btn" onClick={() => setSearchQuery('')}>×</button>
          )}
        </div>

        <div className="archive-filters">
          <div className="filter-group">
            <Filter size={14} style={{ color: 'var(--text-muted)' }} />
            <button 
              className={`filter-btn ${selectedVerdict === 'ALL' ? 'active' : ''}`}
              onClick={() => setSelectedVerdict('ALL')}
            >
              전체 ({reports.length})
            </button>
            <button 
              className={`filter-btn filter-strong-buy ${selectedVerdict === 'STRONG_BUY' ? 'active' : ''}`}
              onClick={() => setSelectedVerdict('STRONG_BUY')}
            >
              🟢 적극매수
            </button>
            <button 
              className={`filter-btn filter-buy ${selectedVerdict === 'BUY' ? 'active' : ''}`}
              onClick={() => setSelectedVerdict('BUY')}
            >
              🔵 분할매수
            </button>
            <button 
              className={`filter-btn filter-neutral ${selectedVerdict === 'NEUTRAL' ? 'active' : ''}`}
              onClick={() => setSelectedVerdict('NEUTRAL')}
            >
              🟡 중립
            </button>
            <button 
              className={`filter-btn filter-unsuitable ${selectedVerdict === 'UNSUITABLE' ? 'active' : ''}`}
              onClick={() => setSelectedVerdict('UNSUITABLE')}
            >
              🔴 투자주의
            </button>
          </div>

          <button className="refresh-btn" onClick={fetchReports} title="새로고침">
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
          </button>
        </div>
      </div>

      {/* 리포트 카드 그리드 리스트 */}
      <div className="archive-grid">
        {loading && reports.length === 0 && (
          <div className="empty-archive">
            <RefreshCw size={24} className="spin" style={{ color: 'var(--accent-cyan)' }} />
            <p>보관된 리포트를 불러오는 중입니다...</p>
          </div>
        )}

        {!loading && filteredReports.length === 0 && (
          <div className="glass-card empty-archive">
            <FolderOpen size={48} style={{ color: 'var(--text-muted)', marginBottom: '12px' }} />
            <h3>보관된 리포트가 없습니다</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', marginTop: '6px' }}>
              '실시간 AI 분석' 메뉴에서 종목을 분석한 후 <strong>[💾 보관함에 저장]</strong> 버튼을 눌러 리포트를 보관해 보세요.
            </p>
          </div>
        )}

        {filteredReports.map((item, idx) => (
          <div 
            key={item.filename || idx} 
            className="glass-card report-card"
            onClick={() => handleOpenReport(item)}
          >
            <div className="report-card-header">
              <div>
                <h4 className="report-card-title">
                  {item.symbol}
                  {item.ticker && <span className="report-card-ticker">({item.ticker})</span>}
                </h4>
                <div className="report-card-date">
                  <Calendar size={12} />
                  <span>{item.created_at || '방금 전'}</span>
                </div>
              </div>
              <div>{getVerdictBadge(item.verdict)}</div>
            </div>

            <div className="report-card-metrics">
              <div className="metric-box">
                <span className="metric-lbl">현재가</span>
                <span className="metric-val">{item.price || 'N/A'}</span>
              </div>
              <div className="metric-box">
                <span className="metric-lbl">PER</span>
                <span className="metric-val">{item.per || 'N/A'}</span>
              </div>
              <div className="metric-box">
                <span className="metric-lbl">PBR</span>
                <span className="metric-val">{item.pbr || 'N/A'}</span>
              </div>
            </div>

            <div className="report-card-footer">
              <span className="card-view-link">
                <FileText size={13} />
                <span>상세 열람 (.md)</span>
              </span>
              <div className="card-action-btns" onClick={(e) => e.stopPropagation()}>
                <button 
                  className="card-icon-btn" 
                  onClick={(e) => handleDownload(e, item)}
                  title=".md 파일 다운로드"
                >
                  <Download size={14} />
                </button>
                <button 
                  className="card-icon-btn delete" 
                  onClick={() => {
                    if (window.confirm(`'${item.symbol}' 리포트를 삭제하시겠습니까?`)) {
                      handleDeleteReport(item.filename);
                    }
                  }}
                  title="삭제"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 리포트 상세 모달 */}
      {isModalOpen && activeReportDetail && (
        <ReportViewerModal
          report={activeReportDetail}
          onClose={() => {
            setIsModalOpen(false);
            setActiveReportDetail(null);
          }}
          onDelete={handleDeleteReport}
        />
      )}
    </div>
  );
}
