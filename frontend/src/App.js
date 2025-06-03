// frontend/src/App.js
import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

function App() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [message, setMessage] = useState('');

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      if (selectedFile.name.endsWith('.txt')) {
        setFile(selectedFile);
        setMessage('');
        setResult(null);
      } else {
        setMessage('TXT 파일만 업로드 가능합니다');
        e.target.value = '';
      }
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setMessage('파일을 선택해주세요');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
      setLoading(true);
      setMessage('처리 중...');
      
      const response = await axios.post(`${API_URL}/api/upload`, formData);
      
      setResult({
        taskId: response.data.task_id,
        stats: response.data.stats,
        message: response.data.message
      });
      setMessage('');
      
    } catch (error) {
      setMessage(error.response?.data?.error || '업로드 실패');
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    if (!result?.taskId) return;
    
    try {
      const response = await axios.get(`${API_URL}/api/download/${result.taskId}`, {
        responseType: 'blob',
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `24년_추출결과_${result.taskId}.txt`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      
    } catch (error) {
      setMessage('다운로드 실패');
    }
  };

  const reset = () => {
    setFile(null);
    setResult(null);
    setMessage('');
    // 파일 input 초기화
    const fileInput = document.querySelector('input[type="file"]');
    if (fileInput) fileInput.value = '';
  };

  return (
    <div className="App">
      <header>
        <h1>📄 24년 모의고사 문제 추출기</h1>
        <p className="subtitle">TXT 파일에서 24년 관련 문제만 추출합니다</p>
      </header>

      <main>
        <div className="guide-section">
          <h2>📌 사용 방법</h2>
          <ol>
            <li>
              <strong>HWP → TXT 변환</strong>
              <ul>
                <li>한글에서 HWP 파일 열기</li>
                <li>파일 → 다른 이름으로 저장</li>
                <li>파일 형식: "텍스트 문서(*.txt)" 선택</li>
                <li>저장</li>
              </ul>
            </li>
            <li><strong>TXT 파일 업로드</strong></li>
            <li><strong>추출 결과 다운로드</strong></li>
          </ol>
        </div>

        {!result ? (
          <div className="upload-section">
            <div className="file-input-wrapper">
              <input
                type="file"
                accept=".txt"
                onChange={handleFileChange}
                disabled={loading}
                id="file-input"
              />
              <label htmlFor="file-input" className="file-label">
                {file ? `📄 ${file.name}` : '파일 선택 (TXT만 가능)'}
              </label>
            </div>
            
            <button 
              onClick={handleUpload} 
              disabled={!file || loading}
              className="upload-button"
            >
              {loading ? '처리 중...' : '🔍 24년 문제 추출'}
            </button>

            {message && <p className="message">{message}</p>}
          </div>
        ) : (
          <div className="result-section">
            <h2>✅ 추출 완료!</h2>
            <p className="result-message">{result.message}</p>
            
            {result.stats && (
              <div className="stats">
                <h3>📊 추출 통계</h3>
                <ul>
                  <li>총 추출: <strong>{result.stats.total_found}개</strong></li>
                  {result.stats.numbered > 0 && (
                    <li>번호 문제: {result.stats.numbered}개</li>
                  )}
                  {result.stats.paragraph > 0 && (
                    <li>문단 형식: {result.stats.paragraph}개</li>
                  )}
                  {result.stats.context > 0 && (
                    <li>문맥 추출: {result.stats.context}개</li>
                  )}
                </ul>
              </div>
            )}
            
            <div className="action-buttons">
              <button onClick={handleDownload} className="download-button">
                📥 결과 다운로드
              </button>
              <button onClick={reset} className="reset-button">
                🔄 새 파일 처리
              </button>
            </div>
          </div>
        )}
      </main>

      <footer>
        <p>💡 TIP: 한글에서 TXT로 저장할 때 인코딩은 "UTF-8" 또는 "한국어(Windows)"를 선택하세요</p>
      </footer>
    </div>
  );
}

export default App;
