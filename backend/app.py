from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import tempfile
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = tempfile.gettempdir()
ALLOWED_EXTENSIONS = {'hwp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

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
        
        # TODO: 실제 HWP 처리 로직 추가
        output_path = process_hwp(filepath, task_id)
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': '처리 완료'
        })
    
    return jsonify({'error': '잘못된 파일 형식'}), 400

def process_hwp(input_path, task_id):
    # 임시 구현 - 나중에 실제 HWP 처리로 교체
    output_path = os.path.join(UPLOAD_FOLDER, f"output_{task_id}.txt")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("24년 모의고사 문제 추출 결과\n")
        f.write("(실제로는 HWP 처리 결과가 들어갑니다)")
    
    return output_path

@app.route('/api/download/<task_id>', methods=['GET'])
def download_file(task_id):
    filepath = os.path.join(UPLOAD_FOLDER, f"output_{task_id}.txt")
    
    if os.path.exists(filepath):
        return send_file(filepath, 
                        as_attachment=True,
                        download_name=f'24년_모의고사_{task_id}.txt')
    
    return jsonify({'error': '파일을 찾을 수 없습니다'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
