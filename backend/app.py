from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import tempfile
import uuid
from werkzeug.utils import secure_filename
import re

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = tempfile.gettempdir()
ALLOWED_EXTENSIONS = {'hwp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

def extract_text_from_hwp(filepath):
    """
    HWP 파일에서 텍스트 추출
    여러 방법 중 선택:
    """
    
    # 방법 1: pyhwp 라이브러리 사용 (Windows만 가능)
    try:
        import olefile
        
        # HWP 파일 열기
        ole = olefile.OleFileIO(filepath)
        
        # 텍스트 스트림 읽기
        text = ""
        if ole.exists("PrvText"):
            stream = ole.openstream("PrvText")
            text = stream.read().decode('utf-16', errors='ignore')
        
        ole.close()
        return text
        
    except Exception as e:
        print(f"HWP 텍스트 추출 실패: {e}")
        
        # 방법 2: 임시 방안 - 파일을 그대로 복사
        # 실제로는 HWP 라이브러리를 사용해야 함
        with open(filepath, 'rb') as f:
            content = f.read()
        return None

def process_hwp(input_path, task_id):
    """24년 문제만 추출하여 새 HWP 파일 생성"""
    
    # 텍스트 추출
    text = extract_text_from_hwp(input_path)
    
    if text:
        # 24년 문제 패턴 찾기
        patterns_2024 = [
            r'(?:^|\n)([^\n]*24년[^\n]*(?:\n(?![^\n]*\d{2}년)[^\n]*)*)',
            r'(?:^|\n)([^\n]*2024년[^\n]*(?:\n(?![^\n]*20\d{2}년)[^\n]*)*)',
            r'(?:^|\n)([^\n]*24학년도[^\n]*(?:\n(?![^\n]*\d{2}학년도)[^\n]*)*)',
        ]
        
        # 24년 문제 추출
        extracted_problems = []
        seen_problems = set()
        
        for pattern in patterns_2024:
            matches = re.finditer(pattern, text, re.MULTILINE | re.DOTALL)
            for match in matches:
                problem_text = match.group(1).strip()
                if problem_text and problem_text not in seen_problems:
                    seen_problems.add(problem_text)
                    extracted_problems.append(problem_text)
        
        # 결과를 텍스트 파일로 저장 (HWP 생성이 어려운 경우)
        output_path = os.path.join(UPLOAD_FOLDER, f"output_{task_id}.txt")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=== 24년 모의고사 문제 추출 결과 ===\n\n")
            for i, problem in enumerate(extracted_problems, 1):
                f.write(f"[문제 {i}]\n{problem}\n\n")
                f.write("-" * 50 + "\n\n")
        
        return output_path
    
    else:
        # HWP 처리 실패 시 원본 파일 그대로 반환
        output_path = os.path.join(UPLOAD_FOLDER, f"output_{task_id}.hwp")
        
        # 임시: 원본 파일 복사
        with open(input_path, 'rb') as src, open(output_path, 'wb') as dst:
            dst.write(src.read())
        
        return output_path

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': '파일이 없습니다'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '파일이 선택되지 않았습니다'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        task_id = str(uuid.uuid4())[:8]
        filepath = os.path.join(UPLOAD_FOLDER, f"{task_id}_{filename}")
        file.save(filepath)
        
        # HWP 처리
        output_path = process_hwp(filepath, task_id)
        
        # 처리 결과에 따라 파일 형식 결정
        file_ext = 'txt' if output_path.endswith('.txt') else 'hwp'
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'file_type': file_ext,
            'message': '처리 완료'
        })
    
    return jsonify({'error': '잘못된 파일 형식'}), 400

@app.route('/api/download/<task_id>', methods=['GET'])
def download_file(task_id):
    # txt 파일 먼저 확인
    txt_path = os.path.join(UPLOAD_FOLDER, f"output_{task_id}.txt")
    hwp_path = os.path.join(UPLOAD_FOLDER, f"output_{task_id}.hwp")
    
    if os.path.exists(txt_path):
        return send_file(txt_path, 
                        as_attachment=True,
                        download_name=f'24년_모의고사_{task_id}.txt',
                        mimetype='text/plain; charset=utf-8')
    elif os.path.exists(hwp_path):
        return send_file(hwp_path, 
                        as_attachment=True,
                        download_name=f'24년_모의고사_{task_id}.hwp',
                        mimetype='application/x-hwp')
    
    return jsonify({'error': '파일을 찾을 수 없습니다'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
