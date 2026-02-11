import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
from werkzeug.utils import secure_filename
from groq import Groq
import json

# Load environment variables
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=BASE_DIR)
CORS(app)

# Security: Limit upload size to 25MB
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024

# API Configuration
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')

if not GROQ_API_KEY:
    print("⚠️  WARNING: API_KEY not set in .env")
else:
    print("✅ Configuration loaded")

# Initialize client
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Upload folder (Vercel uses /tmp as its only writable scratch space)
if os.environ.get('VERCEL'):
    UPLOAD_FOLDER = '/tmp/uploads'
else:
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ============================================================================
# API INTERFACE
# ============================================================================

def perform_voice_capture(audio_path):
    """Voice-to-text conversion via API"""
    if not groq_client:
        raise Exception("Transcription engine not configured.")
    
    with open(audio_path, "rb") as file:
        transcription = groq_client.audio.transcriptions.create(
            file=(audio_path, file.read()),
            model="whisper-large-v3",
            response_format="text",
            language="en",
            temperature=0.0
        )
    
    return transcription

def generate_insight(text, content_type="interaction"):
    """Generate concise insight distillation"""
    if not groq_client:
        raise Exception("Distillation engine not strictly configured. Core services unavailable.")
    
    prompt = f"""You are a customer service analyst. Provide a concise one-line summary of this {content_type}.
Focus on the main topic, customer concern, or outcome.

{content_type.capitalize()}: {text[:4000]}

One-line summary:"""
    
    chat_completion = groq_client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that creates concise one-line summaries of customer interactions."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        model="llama-3.3-70b-versatile",
        temperature=0.7,
        max_tokens=100,
    )
    
    return chat_completion.choices[0].message.content.strip()

# ============================================================================
# FILE PARSING
# ============================================================================

def extract_text_from_file(filepath, filename):
    """Extract text from uploaded file based on extension"""
    ext = os.path.splitext(filename)[1].lower()
    
    try:
        if ext == '.pdf':
            from PyPDF2 import PdfReader
            reader = PdfReader(filepath)
            text = '\n'.join(page.extract_text() or '' for page in reader.pages)
            return text.strip()
        
        elif ext == '.json':
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                data = json.load(f)
            return json.dumps(data, indent=2) if isinstance(data, (dict, list)) else str(data)
        
        else:  # .txt, .csv, .md, .log, etc.
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read().strip()
    except Exception as e:
        print(f"Extraction error ({filename}): {e}")
        return ""

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/process-chat', methods=['POST'])
def process_chat():
    """Process chat text and return summary"""
    try:
        data = request.json
        chat_text = data.get('text', '')
        
        if not chat_text:
            return jsonify({'error': 'No content provided'}), 400
        
        summary = generate_insight(chat_text, "interaction")
        
        return jsonify({
            'success': True,
            'type': 'chat',
            'original_text': chat_text,
            'summary': summary,
            'timestamp': datetime.now().isoformat(),
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/process-file', methods=['POST'])
def process_file():
    """Process uploaded text file and return summary"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        uploaded = request.files['file']
        if uploaded.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        allowed = {'.txt', '.csv', '.json', '.md', '.log', '.pdf'}
        ext = os.path.splitext(uploaded.filename)[1].lower()
        if ext not in allowed:
            return jsonify({'error': f'Unsupported format. Use: {", ".join(allowed)}'}), 400
        
        # Save temporarily with secure filename
        safe_name = secure_filename(uploaded.filename)
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        uploaded.save(filepath)
        
        # Extract text
        text = extract_text_from_file(filepath, uploaded.filename)
        
        # Cleanup
        try: os.remove(filepath)
        except: pass
        
        if not text:
            return jsonify({'error': 'Could not extract text from file'}), 400
        
        # Summarize
        summary = generate_insight(text, "document")
        
        return jsonify({
            'success': True,
            'type': 'chat',
            'original_text': text,
            'summary': summary,
            'timestamp': datetime.now().isoformat(),
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/process-call', methods=['POST'])
def process_call():
    """Process audio call, transcribe, and return summary"""
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        audio_file = request.files['audio']
        
        if audio_file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Save uploaded file safely
        safe_name = secure_filename(audio_file.filename)
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        audio_file.save(filepath)
        
        # Transcribe
        print(f"Decoding {filename}...")
        transcription = perform_voice_capture(filepath)
        
        # Summarize
        print(f"Distilling Insight...")
        summary = generate_insight(transcription, "voice capture")
        
        # Cleanup
        try:
            os.remove(filepath)
        except:
            pass
        
        return jsonify({
            'success': True,
            'type': 'call',
            'transcription': transcription,
            'summary': summary,
            'timestamp': datetime.now().isoformat(),
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'operational',
        'api_ready': bool(GROQ_API_KEY)
    })

@app.route('/', methods=['GET'])
def index():
    """Serve index.html"""
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files safely"""
    allowed_exts = {'.css', '.js', '.ico', '.png', '.jpg', '.svg'}
    ext = os.path.splitext(filename)[1].lower()
    
    if ext in allowed_exts:
        return send_from_directory(BASE_DIR, filename)
    return jsonify({'error': 'Access denied'}), 403

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 Briefly Signal Hub")
    print("="*60)
    print("✓ Backend System: Signal Node Operational")
    print("✓ Deployment Support: Transcription Enabled")
    
    if not GROQ_API_KEY:
        print("\n⚠️  API Key required for operation")
    else:
        print("\n✅ System ready")
    
    print("="*60 + "\n")
    
    app.run(debug=True, port=5000)

# For Vercel
app = app
