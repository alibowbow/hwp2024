# backend/app.py - 실제 HWP 라이브러리 사용 버전

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
ALLOWED_EXTENSIONS = {'hwp', 'hwpx', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

def extract_text_with_pyhwp(filepath):
    """pyhwp 라이브러리 사용"""
    try:
        import pyhwp
        
        # HWP 파일 열기
        hwp = pyhwp.open(filepath)
        
        # 텍스트 추출
        text = hwp.get_text()
        
        hwp.close()
        return text
        
    except Exception as e:
        print(f"pyhwp 실패: {e}")
        return None

def extract_text_with_hwp5(filepath):
    """hwp5 라이브러리 사용 (Linux/Mac)"""
    try:
        from hwp5 import filestructure
        from hwp5.proc import text
        
        # HWP 파일 열기
        hwp5file = filestructure.File(filepath)
        
        # 텍스트 추출
        text_content = []
        for record in text.make_texts(hwp5file):
            text_content.append(record)
        
        return '\n'.join(text_content)
        
    except Exception as e:
        print(f"hwp5 실패: {e}")
        return None

def extract_text_with_python_hwp(filepath):
    """python-hwp 라이브러리 사용"""
    try:
        import hwp
        
        # HWP 문서 열기
        document = hwp.Document(filepath)
        
        # 모든 텍스트 추출
        text_content = []
        for paragraph in document.paragraphs:
            text_content.append(paragraph.text)
        
        return '\n'.join(text_content)
        
    except Exception as e:
        print(f"python-hwp 실패: {e}")
        return None

def extract_text_with_olefile(filepath):
    """olefile로 기본 추출 (구형 HWP)"""
    try:
        import olefile
        import struct
        
        ole = olefile.OleFileIO(filepath)
        text_content = []
        
        # BodyText/Section 스트림 읽기
        dirs = ole.listdir()
        
        for d in dirs:
            if d[0] == 'BodyText':
                sections = [s for s in dirs if s[0] == d[0] and len(s) > 1]
                
                for section in sections:
                    try:
                        data = ole.openstream(section).read()
                        
                        # HWP 텍스트 레코드 파싱
                        pos = 0
                        while pos < len(data):
                            # 레코드 헤더 읽기
                            if pos + 4 > len(data):
                                break
                                
                            header = struct.unpack('<I', data[pos:pos+4])[0]
                            rec_type = header & 0x3ff
                            rec_len = (header >> 20) & 0xfff
                            
                            if rec_len == 0xfff:
                                if pos + 8 > len(data):
                                    break
                                rec_len = struct.unpack('<I', data[pos+4:pos+8])[0]
                                pos += 8
                            else:
                                pos += 4
                            
                            # 텍스트 레코드 (67)
                            if rec_type == 67:
                                text_data = data[pos:pos+rec_len]
                                try:
                                    # UTF-16 디코딩
                                    text = text_data.decode('utf-16-le', errors='ignore')
                                    text = text.replace('\r\n', '\n').replace('\r', '\n')
                                    if text.strip():
                                        text_content.append(text)
                                except:
                                    pass
                            
                            pos += rec_len
                            
                    except Exception as e:
                        print(f"Section 읽기 실패: {e}")
                        continue
        
        # PrvText 스트림 (미리보기 텍스트)
        if not text_content and ole.exists("PrvText"):
            try:
                stream = ole.openstream("PrvText")
                text = stream.read().decode('utf-16-le', errors='ignore')
                text_content.append(text)
            except:
                pass
        
        ole.close()
        return '\n'.join(text_content)
        
    except Exception as e:
        print(f"olefile 실패: {e}")
        return None

def extract_text_from_hwp(filepath):
    """여러 방법으로 HWP 텍스트 추출 시도"""
    
    # 1. pyhwp 시도 (가장 좋음)
    text = extract_text_with_pyhwp(filepath)
    if text:
        print("pyhwp로 추출 성공")
        return text
    
    # 2. hwp5 시도 (Linux/Mac)
    text = extract_text_with_hwp5(filepath)
    if text:
        print("hwp5로 추출 성공")
        return text
    
    # 3. python-hwp 시도
    text = extract_text_with_python_hwp(filepath)
    if text:
        print("python-hwp로 추출 성공")
        return text
    
    # 4. olefile 시도 (기본)
    text = extract_text_with_olefile(filepath)
    if text:
        print("olefile로 추출 성공")
        return text
    
    print("모든 방법 실패")
    return None

def extract_text_from_txt(filepath):
    """TXT 파일 읽기"""
    try:
        encodings = ['utf-8', 'cp949', 'euc-kr', 'utf-16']
        
        for encoding in encodings:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
                
        return None
    except Exception as e:
        print(f"TXT 읽기 실패: {e}")
        return None

def process_file(input_path, task_id):
    """파일 처리"""
    
    # 파일 확장자 확인
    file_ext = input_path.rsplit('.', 1)[1].lower()
    
    if file_ext == 'txt':
        text = extract_text_from_txt(input_path)
    else:  # hwp, hwpx
        text = extract_text_from_hwp(input_path)
    
    output_path = os.path.join(UPLOAD_FOLDER, f"output_{task_id}.txt")
    
    if text and len(text) > 10:
        # 24년 관련 패턴
        patterns_2024 = [
            r'24년', r'2024년', r'24학년도', r'24년도', 
            r"'24", r'2024학년도', r'24학년', r'2024학년'
        ]
        
        # 문장/문단 단위로 추출
        extracted_problems = []
        seen_problems = set()
        
        # 줄 단위 검색
        lines = text.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # 24년 패턴이 있는지 확인
            if any(pattern in line for pattern in patterns_2024):
                # 문제의 시작과 끝 찾기
                start = i
                
                # 빈 줄이나 번호가 나올 때까지 계속 포함
                end = i + 1
                while end < len(lines):
                    next_line = lines[end].strip()
                    
                    # 다음 문제 시작 신호
                    if (next_line == '' and end > start + 2) or \
                       (next_line and next_line[0].isdigit() and '.' in next_line[:5]):
                        break
                    
                    end += 1
                
                # 문제 추출
                problem = '\n'.join(lines[start:end]).strip()
                
                if problem and len(problem) > 20 and problem not in seen_problems:
                    seen_problems.add(problem)
                    extracted_problems.append(problem)
                
                i = end
            else:
                i += 1
        
        # 결과 저장
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=== 24년 모의고사 문제 추출 결과 ===\n\n")
            
            if extracted_problems:
                f.write(f"총 {len(extracted_problems)}개의 24년 관련 문제를 찾았습니다.\n\n")
                for i, problem in enumerate(extracted_problems, 1):
                    f.write(f"[문제 {i}]\n{problem}\n\n")
                    f.write("=" * 60 + "\n\n")
            else:
                f.write("24년 관련 문제를 찾을 수 없습니다.\n\n")
                
                # 디버깅용 - 처음 1000자 출력
                f.write("추출된 텍스트 미리보기:\n")
                f.write("-" * 60 + "\n")
                preview = text[:1000] + "..." if len(text) > 1000 else text
                f.write(preview)
    
    else:
        # 추출 실패
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=== 파일 처리 결과 ===\n\n")
            
            if file_ext in ['hwp', 'hwpx']:
                f.write("HWP 파일에서 텍스트를 추출할 수 없었습니다.\n\n")
                f.write("가능한 원인:\n")
                f.write("1. 암호화된 HWP 파일\n")
                f.write("2. 손상된 파일\n")
                f.write("3. 특수한 HWP 버전\n\n")
                f.write("해결 방법:\n")
                f.write("한글 프로그램에서 파일을 열어 TXT로 저장 후 다시 업로드해주세요.\n")
            else:
                f.write("파일을 읽을 수 없습니다.\n")
    
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
        
        # 파일 처리
        output_path = process_file(filepath, task_id)
        
        # 임시 파일 삭제
        try:
            os.unlink(filepath)
        except:
            pass
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': '처리 완료'
        })
    
    return jsonify({'error': 'HWP, HWPX 또는 TXT 파일만 가능합니다'}), 400

@app.route('/api/download/<task_id>', methods=['GET'])
def download_file(task_id):
    filepath = os.path.join(UPLOAD_FOLDER, f"output_{task_id}.txt")
    
    if os.path.exists(filepath):
        return send_file(filepath, 
                        as_attachment=True,
                        download_name=f'24년_모의고사_{task_id}.txt',
                        mimetype='text/plain; charset=utf-8')
    
    return jsonify({'error': '파일을 찾을 수 없습니다'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
