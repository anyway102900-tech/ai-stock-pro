import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import PromptInput from './components/PromptInput';
import ExecutionConsole from './components/ExecutionConsole';
import ReportViewer from './components/ReportViewer';
import ReportArchive from './components/ReportArchive';
import './App.css';

import krxStocks from './krx_stocks.json';

// 종목코드 -> 종목명 역매핑 테이블 생성
const CODE_TO_NAME = {};
for (const [name, code] of Object.entries(krxStocks)) {
  CODE_TO_NAME[code] = name;
}

export default function App() {
  const [activeTab, setActiveTab] = useState('analyze'); // 'analyze' | 'archive'
  const [logs, setLogs] = useState([]);
  const [report, setReport] = useState(null);
  const [sources, setSources] = useState([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [reportCount, setReportCount] = useState(0);
  const [currentPromptStock, setCurrentPromptStock] = useState('');

  const apiBaseUrl = import.meta.env.VITE_API_URL || 'https://ai-stock-backend-4d3m.onrender.com';

  // 저장된 리포트 개수 조회
  const updateReportCount = async () => {
    try {
      let count = 0;
      const res = await fetch(`${apiBaseUrl}/api/reports`);
      if (res.ok) {
        const data = await res.json();
        count = data.total || 0;
      }
      
      const local = localStorage.getItem('ai_stock_saved_reports');
      if (local) {
        const parsed = JSON.parse(local);
        count = Math.max(count, parsed.length);
      }
      setReportCount(count);
    } catch (e) {
      try {
        const local = localStorage.getItem('ai_stock_saved_reports');
        if (local) setReportCount(JSON.parse(local).length);
      } catch (err) {}
    }
  };

  useEffect(() => {
    updateReportCount();
  }, []);

  const addLog = (tag, message, type = 'info') => {
    const now = new Date();
    const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
    setLogs((prev) => [...prev, { time: timeStr, tag, message, type }]);
  };

  // 리포트 보관함에 저장하기 (.md)
  const handleSaveReport = async (reportText, fallbackPrompt = '') => {
    if (!reportText) return;

    let symbol = '종목분석';
    let ticker = '';

    // 1. 프롬프트 텍스트에서 1차 종목명/코드 추출
    const pText = fallbackPrompt || currentPromptStock;
    if (pText) {
      const codeInPrompt = pText.match(/\b([0-9A-Za-z]{6})\b/);
      if (codeInPrompt && CODE_TO_NAME[codeInPrompt[1]]) {
        ticker = codeInPrompt[1];
        symbol = CODE_TO_NAME[codeInPrompt[1]];
      } else {
        const nameMatch = pText.match(/([가-힣A-Za-z0-9]+)(?:\s*\(([0-9A-Za-z]{6})\))?/);
        if (nameMatch && nameMatch[1] && nameMatch[1].length > 1) {
          symbol = nameMatch[1];
          if (nameMatch[2]) ticker = nameMatch[2];
        }
      }
    }

    // 2. 리포트 본문 대제목에서 추출 (예: # 📋 [SAMG엔터 (419530)] 또는 📋 [클래시스])
    const titleMatch = reportText.match(/📋\s*\[\s*([^(\]\s\n]+)(?:\s*\(([^)]+)\))?\s*\]/);
    if (titleMatch) {
      const rawSym = titleMatch[1].trim();
      const rawTick = titleMatch[2] ? titleMatch[2].trim() : '';
      if (/^[0-9A-Za-z]{6}$/.test(rawSym) && CODE_TO_NAME[rawSym]) {
        symbol = CODE_TO_NAME[rawSym];
        ticker = rawSym;
      } else if (rawSym !== '종목분석' && rawSym !== '종목') {
        symbol = rawSym;
        if (rawTick) ticker = rawTick;
      }
    }

    // 3. 종목코드만 있는 경우 한글 종목명 역변환
    if (/^[0-9A-Za-z]{6}$/.test(symbol) && CODE_TO_NAME[symbol]) {
      ticker = symbol;
      symbol = CODE_TO_NAME[symbol];
    }
    if (!ticker && krxStocks[symbol]) {
      ticker = krxStocks[symbol];
    }

    // 4. 가격 추출
    let price = 'N/A';
    const priceTableMatch = reportText.match(/\|\s*\*\*현재가\*\*\s*\|\s*([0-9,]+원?)/);
    if (priceTableMatch) {
      price = priceTableMatch[1].endsWith('원') ? priceTableMatch[1] : `${priceTableMatch[1]}원`;
    } else {
      const priceTextMatch = reportText.match(/(?:현재가|체결가)[^0-9\n]*([0-9,]+원)/);
      if (priceTextMatch) price = priceTextMatch[1];
    }

    // 5. PER / PBR 추출
    let per = 'N/A';
    let pbr = 'N/A';
    const perPbrMatch = reportText.match(/\|\s*\*\*PER\s*\/\s*PBR\*\*\s*\|\s*([0-9.]+배?)\s*\/\s*([0-9.]+배?)/);
    if (perPbrMatch) {
      per = perPbrMatch[1].includes('배') ? perPbrMatch[1] : `${perPbrMatch[1]}배`;
      pbr = perPbrMatch[2].includes('배') ? perPbrMatch[2] : `${perPbrMatch[2]}배`;
    } else {
      const perMatch = reportText.match(/PER[^0-9\n]*([0-9.]+배)/);
      if (perMatch) per = perMatch[1];
      const pbrMatch = reportText.match(/PBR[^0-9\n]*([0-9.]+배)/);
      if (pbrMatch) pbr = pbrMatch[1];
    }

    // 6. 투자 등급 추출
    let verdict = '분석완료';
    if (reportText.includes('적극 매수') || reportText.includes('Strong Buy')) verdict = '적극매수';
    else if (reportText.includes('분할 매수') || reportText.includes('Buy')) verdict = '분할매수';
    else if (reportText.includes('투자 부적합') || reportText.includes('Unsuitable')) verdict = '투자주의';
    else if (reportText.includes('중립') || reportText.includes('Neutral')) verdict = '중립';

    const meta = {
      symbol,
      ticker,
      verdict,
      price,
      per,
      pbr,
      created_at: new Date().toLocaleString()
    };

    // 1. 백엔드 저장 API 호출
    let savedFilename = '';
    try {
      const res = await fetch(`${apiBaseUrl}/api/reports`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, content: reportText, meta })
      });
      if (res.ok) {
        const data = await res.json();
        savedFilename = data.report?.filename || '';
      }
    } catch (err) {
      console.warn('백엔드 저장 실패, 로컬 스토리지에 백업 저장:', err);
    }

    // 2. LocalStorage 동기화 백업
    try {
      const localItem = {
        filename: savedFilename || `${Date.now()}_${symbol}_${verdict}.md`,
        symbol,
        ticker,
        verdict,
        price,
        per,
        pbr,
        content: reportText,
        created_at: new Date().toLocaleString()
      };
      const existing = JSON.parse(localStorage.getItem('ai_stock_saved_reports') || '[]');
      existing.unshift(localItem);
      localStorage.setItem('ai_stock_saved_reports', JSON.stringify(existing));
    } catch (e) {
      console.error('LocalStorage 저장 오류:', e);
    }

    setIsSaved(true);
    updateReportCount();
  };

  const handleExecute = async (prompt, forceRefresh) => {
    setIsAnalyzing(true);
    setIsSaved(false);
    setLogs([]);
    setReport(null);
    setSources([]);

    addLog('INFO', 'RICE 프롬프트 수신 및 요구조건 분석 시작', 'info');

    let backendSuccess = false;

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 90000);

      let response = null;
      try {
        response = await fetch(`${apiBaseUrl}/api/analyze`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt, force_refresh: forceRefresh }),
          signal: controller.signal
        });
      } catch (err) {
        console.warn('1차 API 호출 실패, 백업 로컬 주소로 재시도:', err);
      }

      if (!response || !response.ok) {
        try {
          response = await fetch(`http://127.0.0.1:8000/api/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt, force_refresh: forceRefresh }),
            signal: controller.signal
          });
        } catch (err) {
          console.error('로컬 백엔드 직접 연결 실패:', err);
        }
      }

      clearTimeout(timeoutId);

      if (response && response.ok) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const dataStr = line.replace('data: ', '').trim();
              if (dataStr === '[DONE]') break;
              try {
                const parsed = JSON.parse(dataStr);
                if (parsed.type === 'log') {
                  addLog(parsed.tag, parsed.message, parsed.level || 'info');
                } else if (parsed.type === 'result') {
                  setReport(parsed.report);
                  setSources(parsed.sources || []);
                  backendSuccess = true;
                  // 분석 완료 시 자동 저장
                  handleSaveReport(parsed.report);
                }
              } catch (e) {
                console.error('JSON 파싱 오류:', e, dataStr);
              }
            }
          }
        }
      } else {
        addLog('ERROR', `백엔드 서버 응답 오류 (상태 코드: ${response?.status || '연결불가'})`, 'error');
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        addLog('ERROR', '요청 시간이 초과되었습니다 (90초 제한). 백엔드 서버가 절전 모드에서 깨어나는 중일 수 있으니 잠시 후 다시 시도해 주세요.', 'error');
      } else {
        addLog('ERROR', `백엔드 통신 오류: ${err.message}`, 'error');
      }
    }

    if (!backendSuccess && !report) {
      addLog('WARN', '실시간 팩트체크 리포트를 생성하지 못했습니다. 상단 [캐시 무시 강제 갱신]을 켜고 다시 실행해 주세요.', 'warn');
    }

    setIsAnalyzing(false);
  };

  return (
    <div className="dashboard-container">
      <Header 
        status={isAnalyzing ? 'analyzing' : 'ready'} 
        activeTab={activeTab}
        onTabChange={setActiveTab}
        reportCount={reportCount}
      />

      {activeTab === 'analyze' && (
        <>
          <PromptInput onExecute={handleExecute} isAnalyzing={isAnalyzing} />
          <ExecutionConsole logs={logs} isAnalyzing={isAnalyzing} />
          <ReportViewer 
            report={report} 
            sources={sources} 
            isAnalyzing={isAnalyzing} 
            onSaveReport={handleSaveReport}
            isSaved={isSaved}
          />
        </>
      )}

      {activeTab === 'archive' && (
        <ReportArchive apiBaseUrl={apiBaseUrl} />
      )}
    </div>
  );
}
