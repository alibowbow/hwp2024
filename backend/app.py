# backend/app.py 수정 버전 - 더 나은 HWP 처리

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import tempfile
import uuid
from werkzeug.utils import secure_filename
import re
import zipfile
import xml.etree.ElementTree as ET

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = tempfile.gettempdir()
ALLOWED_EXTENSIONS = {'hwp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

def extract_text_from_hwpx(filepath):
    """HWPX (최신 한글) 파일에서 텍스트 추출"""
    try:
        text_content = []
        
        # HWPX는 실제로 ZIP 파일
        with zipfile.ZipFile(filepath, 'r') as z:
            # Contents 폴더의 section XML 파일들 찾기
            for filename in z.namelist():
                if filename.startswith('Contents/section') and filename.endswith('.xml'):
                    with z.open(filename) as f:
                        content = f.read().decode('utf-8')
                        
                        # XML 파싱
                        try:
                            root = ET.fromstring(content)
                            
                            # 텍스트 요소 찾기 (네임스페이스 무시)
                            for elem in root.iter():
                                if elem.text and elem.text.strip():
                                    text_content.append(elem.text.strip())
                        except:
                            # XML 파싱 실패시 정규식으로 텍스트 추출
                            text_matches = re.findall(r'<hp:t[^>]*>([^<]+)</hp:t>', content)
                            text_content.extend(text_matches)
        
        return '\n'.join(text_content)
        
    except zipfile.BadZipFile:
        # ZIP 파일이 아닌 경우 (구형 HWP)
        return None
    except Exception as e:
        print(f"HWPX 추출 실패: {e}")
        return None

def extract_text_from_hwp5(filepath):
    """HWP 5.0 (구형) 파일에서 텍스트 추출"""
    try:
        import olefile
        
        ole = olefile.OleFileIO(filepath)
        text_content = []
        
        # PrvText 스트림 (미리보기 텍스트)
        if ole.exists("PrvText"):
            stream = ole.openstream("PrvText")
            text = stream.read().decode('utf-16-le', errors='ignore')
            text_content.append(text)
        
        # BodyText 섹션들
        for entry in ole.listdir():
            if entry[0] == "BodyText":
                for section in ole.listdir(entry):
                    if section[0].startswith("Section"):
                        try:
                            stream_path = '/'.join(section)
                            stream = ole.openstream(stream_path)
                            # HWP 바이너리 포맷 파싱 (간단한 버전)
                            data = stream.read()
                            # 유니코드 텍스트 찾기
                            text_matches = re.findall(b'(?:[\x20-\x7E]|[\xAC00-\xD7AF])+', data)
                            for match in text_matches:
                                try:
                                    decoded = match.decode('utf-8', errors='ignore')
                                    if len(decoded) > 3:  # 짧은 문자열 제외
                                        text_content.append(decoded)
                                except:
                                    pass
                        except:
                            pass
        
        ole.close()
        return '\n'.join(text_content)
        
    except Exception as e:
        print(f"HWP5 추출 실패: {e}")
        return None

def extract_text_from_hwp_any(filepath):
    """모든 버전의 HWP 파일에서 텍스트 추출 시도"""
    
    # 1. HWPX (최신 버전) 시도
    text = extract_text_from_hwpx(filepath)
    if text:
        return text
    
    # 2. HWP 5.0 (구형) 시도
    text = extract_text_from_hwp5(filepath)
    if text:
        return text
    
    # 3. 마지막 수단 - 바이너리에서 한글 찾기
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
            
        # UTF-8로 인코딩된 한글 찾기
        korean_pattern = re.compile(b'[\xEA-\xED][\x80-\xBF][\x80-\xBF]')
        matches = korean_pattern.findall(data)
        
        text_parts = []
        for match in matches:
            try:
                decoded = match.decode('utf-8', errors='ignore')
                text_parts.append(decoded)
            except:
                pass
        
        # 연속된 한글 텍스트 찾기
        text = ''.join(text_parts)
        # 의미있는 단어/문장 추출
        words = re.findall(r'[가-힣]{2,}', text)
        
        return ' '.join(words)
        
    except Exception as e:
        print(f"바이너리 추출 실패: {e}")
        return None

def process_hwp(input_path, task_id):
    """24년 문제만 추출하여 결과 생성"""
    
    # 텍스트 추출
    text = extract_text_from_hwp_any(input_path)
    
    if text and len(text) > 10:  # 의미있는 텍스트가 추출된 경우
        # 24년 관련 패턴
        patterns_2024 = [
            r'(24년[^.!?\n]*[.!?])',
            r'(2024년[^.!?\n]*[.!?])',
            r'(24학년도[^.!?\n]*[.!?])',
            r'(24년도[^.!?\n]*[.!?])',
            r'(\'24[^.!?\n]*[.!?])',
            # 문장 단위가 아닌 단락 단위 추출
            r'(24년[^\n]{10,500})',
            r'(2024년[^\n]{10,500})',
        ]
        
        # 24년 문제 추출
        extracted_problems = []
        seen_problems = set()
        
        for pattern in patterns_2024:
            matches = re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                problem_text = match.group(1).strip()
                # 중복 제거 및 최소 길이 확인
                if problem_text and len(problem_text) > 20 and problem_text not in seen_problems:
                    seen_problems.add(problem_text)
                    extracted_problems.append(problem_text)
        
        # 결과 저장
        output_path = os.path.join(UPLOAD_FOLDER, f"output_{task_id}.txt")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=== 24년 모의고사 문제 추출 결과 ===\n\n")
            
            if extracted_problems:
                f.write(f"총 {len(extracted_problems)}개의 24년 관련 내용을 찾았습니다.\n\n")
                for i, problem in enumerate(extracted_problems, 1):
                    f.write(f"[{i}번]\n{problem}\n\n")
                    f.write("-" * 50 + "\n\n")
            else:
                f.write("24년 관련 문제를 찾을 수 없습니다.\n")
                f.write("\n추출된 전체 텍스트 미리보기:\n")
                f.write("-" * 50 + "\n")
                f.write(text[:1000] + "..." if len(text) > 1000 else text)
        
        return output_path
    
    else:
        # 텍스트 추출 실패 - 디버깅 정보 포함
        output_path = os.path.join(UPLOAD_FOLDER, f"output_{task_id}_debug.txt")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=== HWP 파일 분석 결과 ===\n\n")
            f.write("텍스트 추출에 실패했습니다.\n\n")
            
            # 파일 정보
            f.write(f"파일 크기: {os.path.getsize(input_path)} bytes\n")
            
            # 파일 시그니처 확인
            with open(input_path, 'rb') as hwp:
                header = hwp.read(32)
                f.write(f"파일 헤더: {header[:8]}\n")
                
                if header[:8] == b'HWP Document':
                    f.write("-> 구형 HWP 파일 (HWP 5.0)\n")
                elif header[:2] == b'PK':
                    f.write("-> 신형 HWPX 파일 (ZIP 기반)\n")
                else:
                    f.write("-> 알 수 없는 형식\n")
            
            f.write("\n현재 이 서버에서는 HWP 파일 처리가 제한적입니다.\n")
            f.write("다음 방법을 시도해보세요:\n")
            f.write("1. HWP 파일을 TXT나 DOCX로 변환 후 업로드\n")
            f.write("2. 한글 프로그램에서 '다른 이름으로 저장' > 'TXT' 선택\n")
        
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
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': '처리 완료'
        })
    
    return jsonify({'error': '잘못된 파일 형식'}), 400

@app.route('/api/download/<task_id>', methods=['GET'])
def download_file(task_id):
    # 가능한 파일들 확인
    for suffix in ['', '_debug']:
        filepath = os.path.join(UPLOAD_FOLDER, f"output_{task_id}{suffix}.txt")
        if os.path.exists(filepath):
            return send_file(filepath, 
                            as_attachment=True,
                            download_name=f'24년_모의고사_{task_id}.txt',
                            mimetype='text/plain; charset=utf-8')
    
    return jsonify({'error': '파일을 찾을 수 없습니다'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
