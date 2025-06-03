import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

function App() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [taskId, setTaskId] = useState(null);
  const [message, setMessage] = useState('');

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile && selectedFile.name.endsWith('.hwp')) {
      setFile(selectedFile);
      setMessage('');
    } else {
      setMessage('HWP 파일만 선택 가능합니다');
      e.target.value = '';
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
      
      setTaskId(response.data.task_id);
      setMessage('처리 완료! 다운로드 버튼을 클릭하세요.');
      
    } catch (error) {
      setMessage(error.response?.data?.error || '업로드 실패');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/download/${taskId}`, {
        responseType: 'blob',
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `24년_모의고사_${taskId}.txt`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      
    } catch (error) {
      setMessage('다운로드 실패');
    }
  };

  return (
    <div className="App">
      <h1>📄 HWP 24년 문제 추출기</h1>
      
      <div className="upload-section">
        <input
          type="file"
          accept=".hwp"
          onChange={handleFileChange}
          disabled={loading}
        />
        
        <button onClick={handleUpload} disabled={!file || loading}>
          {loading ? '처리 중...' : '추출 시작'}
        </button>
      </div>

      {message && <p className="message">{message}</p>}

      {taskId && (
        <button onClick={handleDownload} className="download-btn">
          📥 다운로드
        </button>
      )}
    </div>
  );
}

export default App;
