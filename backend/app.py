# backend/app.py - TXT 파일 전용 처리

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
ALLOWED_EXTENSIONS = {'txt'}  # TXT만 허용

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'txt-processor'})

def read_txt_file(filepath):
    """TXT 파일 읽기 (다양한 인코딩 지원)"""
    encodings = ['utf-8', 'cp949', 'euc-kr', 'utf-16', 'latin-1']
    
    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                content = f.read()
                if content:
                    print(f"파일 인코딩: {encoding}")
                    return content
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    # 모든 인코딩 실패시
    print("텍스트 파일을 읽을 수 없습니다.")
    return None

def extract_24_year_content(text):
    """24년 관련 내용 추출"""
    if not text:
        return []
    
    # 24년 관련 패턴들
    year_patterns = [
        r'24년', r'2024년', r'24학년도', r'24년도', 
        r"'24", r'2024학년도', r'２４년', r'24학년',
        r'2024-', r'24-', r'2024\.', r'24\.'
    ]
    
    extracted_content = []
    seen_content = set()
    
    # 방법 1: 문제 번호가 있는 경우
    # 예: "1. 문제내용" 또는 "문제 1)" 형식
    problem_pattern = r'(?:^|\n)\s*(?:문제\s*)?(\d+)[.)]\s*([^\n]+(?:\n(?!\s*(?:문제\s*)?\d+[.)])[^\n]+)*)'
    problems = re.finditer(problem_pattern, text, re.MULTILINE)
    
    for match in problems:
        problem_text = match.group(0).strip()
        # 24년 패턴이 포함된 문제만 추출
        if any(re.search(pattern, problem_text, re.IGNORECASE) for pattern in year_patterns):
            if problem_text not in seen_content:
                seen_content.add(problem_text)
                extracted_content.append({
                    'type': 'numbered',
                    'content': problem_text
                })
    
    # 방법 2: 문단 단위로 추출 (번호가 없는 경우)
    if not extracted_content:
        # 빈 줄로 구분된 문단들
        paragraphs = re.split(r'\n\s*\n', text)
        
        for para in paragraphs:
            para = para.strip()
            if not para or len(para) < 20:  # 너무 짧은 문단 제외
                continue
            
            # 24년 패턴이 포함된 문단
            if any(re.search(pattern, para, re.IGNORECASE) for pattern in year_patterns):
                if para not in seen_content:
                    seen_content.add(para)
                    extracted_content.append({
                        'type': 'paragraph',
                        'content': para
                    })
    
    # 방법 3: 줄 단위로 추출 (마지막 수단)
    if not extracted_content:
        lines = text.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # 24년 패턴이 있는 줄 발견
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in year_patterns):
                # 앞뒤 문맥 포함 (위 2줄, 아래 5줄)
                start = max(0, i - 2)
                end = min(len(lines), i + 6)
                
                # 연속된 빈 줄 제거하면서 문맥 추출
                context_lines = []
                for j in range(start, end):
                    if j < len(lines):
                        line_text = lines[j].strip()
                        if line_text:  # 빈 줄 제외
                            context_lines.append(line_text)
                
                if context_lines:
                    context = '\n'.join(context_lines)
                    if context not in seen_content and len(context) > 30:
                        seen_content.add(context)
                        extracted_content.append({
                            'type': 'context',
                            'content': context
                        })
                
                # 다음 검색 위치
                i = end
            else:
                i += 1
    
    return extracted_content

def create_output_file(extracted_content, original_filename, task_id):
    """추출 결과를 새 TXT 파일로 생성"""
    output_path = os.path.join(UPLOAD_FOLDER, f"output_{task_id}.txt")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        # 헤더
        f.write("=" * 70 + "\n")
        f.write("24년 모의고사 문제 추출 결과\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"원본 파일: {original_filename}\n")
        f.write(f"추출된 항목: {len(extracted_content)}개\n")
        f.write("=" * 70 + "\n\n")
        
        if extracted_content:
            # 타입별로 그룹화
            numbered_items = [item for item in extracted_content if item['type'] == 'numbered']
            paragraph_items = [item for item in extracted_content if item['type'] == 'paragraph']
            context_items = [item for item in extracted_content if item['type'] == 'context']
            
            # 번호가 있는 문제들
            if numbered_items:
                f.write("[ 번호가 있는 문제 ]\n")
                f.write("-" * 70 + "\n\n")
                for i, item in enumerate(numbered_items, 1):
                    f.write(item['content'])
                    f.write("\n\n" + "-" * 50 + "\n\n")
            
            # 문단 형식
            if paragraph_items:
                if numbered_items:
                    f.write("\n\n")
                f.write("[ 문단 형식 문제 ]\n")
                f.write("-" * 70 + "\n\n")
                for i, item in enumerate(paragraph_items, 1):
                    f.write(f"[{i}]\n")
                    f.write(item['content'])
                    f.write("\n\n" + "-" * 50 + "\n\n")
            
            # 문맥 추출
            if context_items:
                if numbered_items or paragraph_items:
                    f.write("\n\n")
                f.write("[ 문맥 기반 추출 ]\n")
                f.write("-" * 70 + "\n\n")
                for i, item in enumerate(context_items, 1):
                    f.write(f"[추출 {i}]\n")
                    f.write(item['content'])
                    f.write("\n\n" + "-" * 50 + "\n\n")
        
        else:
            f.write("24년 관련 내용을 찾을 수 없습니다.\n\n")
            f.write("확인사항:\n")
            f.write("- 파일에 '24년', '2024년', '24학년도' 등의 키워드가 포함되어 있나요?\n")
            f.write("- 텍스트 인코딩이 올바른가요?\n")
            f.write("- 한글 프로그램에서 TXT로 저장할 때 '텍스트 문서' 형식을 선택했나요?\n")
    
    return output_path

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': '파일이 없습니다'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '파일이 선택되지 않았습니다'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({
            'error': 'TXT 파일만 업로드 가능합니다',
            'hint': '한글에서 "파일 > 다른 이름으로 저장 > 텍스트 문서(*.txt)"로 저장 후 업로드하세요'
        }), 400
    
    if file:
        filename = secure_filename(file.filename)
        task_id = str(uuid.uuid4())[:8]
        
        # 파일 저장
        filepath = os.path.join(UPLOAD_FOLDER, f"{task_id}_{filename}")
        file.save(filepath)
        
        try:
            # TXT 파일 읽기
            text = read_txt_file(filepath)
            
            if not text:
                return jsonify({
                    'error': '파일을 읽을 수 없습니다',
                    'hint': '파일 인코딩을 확인해주세요'
                }), 400
            
            # 24년 내용 추출
            extracted = extract_24_year_content(text)
            
            # 결과 파일 생성
            output_path = create_output_file(extracted, filename, task_id)
            
            # 통계 정보
            stats = {
                'total_found': len(extracted),
                'numbered': len([x for x in extracted if x['type'] == 'numbered']),
                'paragraph': len([x for x in extracted if x['type'] == 'paragraph']),
                'context': len([x for x in extracted if x['type'] == 'context'])
            }
            
            return jsonify({
                'success': True,
                'task_id': task_id,
                'message': f"{len(extracted)}개의 24년 관련 내용을 찾았습니다",
                'stats': stats
            })
            
        except Exception as e:
            return jsonify({
                'error': f'처리 중 오류 발생: {str(e)}'
            }), 500
            
        finally:
            # 원본 파일 삭제
            try:
                os.unlink(filepath)
            except:
                pass

@app.route('/api/download/<task_id>', methods=['GET'])
def download_file(task_id):
    filepath = os.path.join(UPLOAD_FOLDER, f"output_{task_id}.txt")
    
    if os.path.exists(filepath):
        return send_file(
            filepath,
            as_attachment=True,
            download_name=f'24년_추출결과_{task_id}.txt',
            mimetype='text/plain; charset=utf-8'
        )
    
    return jsonify({'error': '파일을 찾을 수 없습니다'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
