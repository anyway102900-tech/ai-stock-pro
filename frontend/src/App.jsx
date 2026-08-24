import React, { useState } from 'react';
import Header from './components/Header';
import PromptInput from './components/PromptInput';
import ExecutionConsole from './components/ExecutionConsole';
import ReportViewer from './components/ReportViewer';
import './App.css';

export default function App() {
  const [logs, setLogs] = useState([]);
  const [report, setReport] = useState(null);
  const [sources, setSources] = useState([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const addLog = (tag, message, type = 'info') => {
    const now = new Date();
    const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
    setLogs((prev) => [...prev, { time: timeStr, tag, message, type }]);
  };

  const handleExecute = async (prompt, forceRefresh) => {
    setIsAnalyzing(true);
    setLogs([]);
    setReport(null);
    setSources([]);

    addLog('INFO', 'RICE 프롬프트 수신 및 요구조건 분석 시작', 'info');

    let backendSuccess = false;

    try {
      // 백엔드 API 호출 (환경변수 VITE_API_URL 지원 또는 기본 상대경로)
      const apiBaseUrl = import.meta.env.VITE_API_URL || '';
      
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 90000); // 90초 타임아웃

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

      // 외부 터널이나 프록시 405 오류 시 로컬 백엔드 직접 연결 폴백
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
                }
              } catch (e) {
                console.error('JSON 파싱 오류:', e, dataStr);
              }
            }
          }
        }
      } else {
        addLog('ERROR', `백엔드 서버 응답 오류 (상태 코드: ${response.status})`, 'error');
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
      <Header status={isAnalyzing ? 'analyzing' : 'ready'} />
      <PromptInput onExecute={handleExecute} isAnalyzing={isAnalyzing} />
      <ExecutionConsole logs={logs} isAnalyzing={isAnalyzing} />
      <ReportViewer report={report} sources={sources} isAnalyzing={isAnalyzing} />
    </div>
  );
}
