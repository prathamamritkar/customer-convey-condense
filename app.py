import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
from werkzeug.utils import secure_filename
from groq import Groq
from deepgram import DeepgramClient
from elevenlabs.client import ElevenLabs
import json

# Load environment variables
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=BASE_DIR)
CORS(app)

# Security: Limit upload size to 25MB
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# API Configuration
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')

if not GROQ_API_KEY:
    print("⚠️  WARNING: GROQ_API_KEY not set. Primary engine offline.")
else:
    print("✅ Groq Engine: Ready")

# Initialize clients
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY', '')
deepgram_client = DeepgramClient(api_key=DEEPGRAM_API_KEY) if DEEPGRAM_API_KEY else None

ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY', '')
elevenlabs_client = ElevenLabs(api_key=ELEVENLABS_API_KEY) if ELEVENLABS_API_KEY else None

MURF_API_KEY = os.getenv('MURF_API_KEY', '')
# Murf is primarily TTS, keeping it ready for future voice conveyance if needed

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
    """Voice-to-text conversion via API with multi-provider fallback and speaker diarization"""
    
    # attempt 1: ElevenLabs Scribe - PRIMARY (best quality, speaker diarization)
    if elevenlabs_client:
        try:
            print("--- Attempting ElevenLabs Scribe Transcription ---")
            with open(audio_path, "rb") as audio_file:
                # Use ElevenLabs Scribe for transcription
                response = elevenlabs_client.scribe.transcribe(
                    audio=audio_file,
                    model="scribe_v2",
                    language="en",
                    diarize=True,  # Enable speaker diarization
                )
                
                # Format response with speaker labels if available
                if hasattr(response, 'segments') and response.segments:
                    formatted_transcript = []
                    for segment in response.segments:
                        speaker = f"Speaker {segment.speaker}" if hasattr(segment, 'speaker') else "Speaker"
                        text = segment.text if hasattr(segment, 'text') else str(segment)
                        formatted_transcript.append(f"{speaker}: {text}")
                    
                    if formatted_transcript:
                        return "\n\n".join(formatted_transcript)
                
                # Fallback to plain text if available
                if hasattr(response, 'text'):
                    return response.text
                return str(response)
                
        except Exception as e:
            print(f"⚠️ ElevenLabs Transcription Failed: {e}")
    
    # attempt 2: Deepgram (Nova-2) with speaker diarization - FALLBACK
    if deepgram_client:
        try:
            print("--- Attempting Deepgram Transcription with Diarization (Fallback) ---")
            with open(audio_path, "rb") as file:
                buffer_data = file.read()
            
            # v3 SDK (5.x) with diarization enabled
            response = deepgram_client.listen.v1.media.transcribe_file(
                request=buffer_data,
                model="nova-2",
                smart_format=True,
                diarize=True,  # Enable speaker diarization
                punctuate=True,
                utterances=True,  # Get speaker-separated utterances
            )
            
            # Format transcription with speaker labels
            if hasattr(response, 'results') and response.results.channels:
                channel = response.results.channels[0]
                
                # Check if we have utterances (speaker-separated segments)
                if hasattr(response.results, 'utterances') and response.results.utterances:
                    formatted_transcript = []
                    for utterance in response.results.utterances:
                        speaker = f"Speaker {utterance.speaker}"
                        text = utterance.transcript
                        formatted_transcript.append(f"{speaker}: {text}")
                    
                    if formatted_transcript:
                        return "\n\n".join(formatted_transcript)
                
                # Fallback to regular transcript if no utterances
                if channel.alternatives:
                    return channel.alternatives[0].transcript
                    
        except Exception as e:
            print(f"⚠️ Deepgram Transcription Failed: {e}")

    # attempt 3: Groq (Whisper-large-v3) - FINAL FALLBACK (no diarization support)
    if groq_client:
        try:
            print("--- Attempting Groq Transcription (Final Fallback) ---")
            with open(audio_path, "rb") as file:
                # Try verbose_json format to get word-level timestamps
                transcription = groq_client.audio.transcriptions.create(
                    file=(audio_path, file.read()),
                    model="whisper-large-v3",
                    response_format="verbose_json",
                    language="en",
                    temperature=0.0
                )
            
            # Groq returns verbose JSON with segments
            if hasattr(transcription, 'text'):
                return transcription.text
            return str(transcription)
        except Exception as e:
            print(f"⚠️ Groq Transcription Failed: {e}")

    raise Exception("All transcription engines failed or are not configured.")

def generate_insight(text, content_type="interaction"):
    """Generate concise insight distillation with fallback to Deepgram"""
    
    # attempt 1: Groq (Llama-3.3-70b-versatile)
    if groq_client:
        try:
            print(f"--- Attempting Groq Insight Generation ({content_type}) ---")
            
            # Model Constants
            MODEL_ID = "llama-3.3-70b-versatile"
            # Safe character limit (~25k tokens) to leave room for response and prompt
            # Llama 3.3 has 128k context, so we can be generous, but let's be safe with 100k chars per chunk
            CHUNK_SIZE = 100000 
            
            def get_groq_completion(input_text):
                prompt = f"""You are a customer service analyst. Provide a concise one-line summary of this {content_type}.
Focus on the main topic, customer concern, or outcome.

{content_type.capitalize()}: {input_text}

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
                    model=MODEL_ID,
                    temperature=0.7,
                    max_tokens=150,
                )
                return chat_completion.choices[0].message.content.strip()

            # Logic: If text is within limit, process directly.
            # If text > limit, chunk it -> summarize chunks -> summarize the summaries.
            
            if len(text) <= CHUNK_SIZE:
                return get_groq_completion(text)
            
            print(f"Input text length ({len(text)}) exceeds chunk limit ({CHUNK_SIZE}). Initiating chunked processing...")
            
            # Simple character-based chunking (could be improved with token-aware splitting)
            chunks = [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]
            chunk_summaries = []
            
            for i, chunk in enumerate(chunks):
                print(f"Processing chunk {i+1}/{len(chunks)}...")
                try:
                    summary = get_groq_completion(chunk)
                    chunk_summaries.append(summary)
                except Exception as e:
                    print(f"Error processing chunk {i+1}: {e}")
                    chunk_summaries.append("[Chunk processing failed]")
            
            # Consolidate summaries
            combined_summary_text = "\n".join(chunk_summaries)
            print("Generating final consolidated summary...")
            
            final_prompt = f"""You are a lead analyst. Below are summaries of different parts of a long {content_type}.
Synthesize them into a single, cohesive one-line summary that captures the overall essence.

Partial Summaries:
{combined_summary_text}

Final One-line summary:"""

            final_completion = groq_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that consolidates multiple summaries into one concise insight."
                    },
                    {
                        "role": "user",
                        "content": final_prompt
                    }
                ],
                model=MODEL_ID,
                temperature=0.7,
                max_tokens=200,
            )
            return final_completion.choices[0].message.content.strip()

        except Exception as e:
            print(f"⚠️ Groq Insight Generation Failed: {e}")

    # attempt 2: Deepgram (Text Intelligence Summarization)
    if deepgram_client:
        try:
            print("--- Attempting Deepgram Insight Generation (Fallback) ---")
            
            # Deepgram often returns the original text if it's very short.
            # We can handle very short text ourselves to save latency/quota.
            if len(text.split()) < 10:
                print("Text too short for summarization, returning as is.")
                return text.strip()

            # v3 SDK (5.x) usage for Text Intelligence
            response = deepgram_client.read.v1.text.analyze(
                request={'buffer': text},
                summarize=True,
                language="en",
            )
            
            # Robust extraction based on Deepgram Python SDK v3+ structure
            if hasattr(response, 'results'):
                results = response.results
                # Check for direct summary property (Text Intelligence)
                if hasattr(results, 'summary') and results.summary:
                    return results.summary
                # Check for nested channel-based summary (alternatives)
                if hasattr(results, 'channels') and results.channels:
                    alt = results.channels[0].alternatives[0]
                    if hasattr(alt, 'summaries') and alt.summaries:
                        return alt.summaries[0].summary
                    if hasattr(alt, 'summary') and alt.summary:
                        return alt.summary

            # Fallback if we got a response but couldn't parse it
            if str(response):
                print(f"Deepgram response received but not parsed: {response}")
                
        except Exception as e:
            print(f"⚠️ Deepgram Insight Generation Failed: {e}")

    raise Exception("All distillation engines failed or are not configured.")

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
            'timestamp': datetime.utcnow().isoformat() + 'Z',
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
            'timestamp': datetime.utcnow().isoformat() + 'Z',
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
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'operational',
        'transcription': {
            'primary': 'elevenlabs' if ELEVENLABS_API_KEY else 'deepgram' if DEEPGRAM_API_KEY else 'groq' if GROQ_API_KEY else None,
            'diarization': bool(ELEVENLABS_API_KEY or DEEPGRAM_API_KEY),
            'fallback_chain': [
                provider for provider in ['elevenlabs', 'deepgram', 'groq']
                if (provider == 'elevenlabs' and ELEVENLABS_API_KEY) or
                   (provider == 'deepgram' and DEEPGRAM_API_KEY) or
                   (provider == 'groq' and GROQ_API_KEY)
            ]
        },
        'summarization': {
            'primary': 'groq' if GROQ_API_KEY else 'deepgram' if DEEPGRAM_API_KEY else None,
            'fallback': 'deepgram' if GROQ_API_KEY and DEEPGRAM_API_KEY else None
        },
        'api_ready': bool(ELEVENLABS_API_KEY or DEEPGRAM_API_KEY or GROQ_API_KEY),
        'fallbacks': {
            'elevenlabs': bool(ELEVENLABS_API_KEY),
            'deepgram': bool(DEEPGRAM_API_KEY),
            'groq': bool(GROQ_API_KEY),
            'murf': bool(MURF_API_KEY)
        }
    })

@app.route('/api/elevenlabs-token', methods=['GET'])
def get_elevenlabs_token():
    """Generate single-use token for ElevenLabs client-side SDK"""
    if not elevenlabs_client:
        return jsonify({'error': 'ElevenLabs not configured'}), 503
    
    try:
        # Generate single-use token for realtime scribe (expires in 15 minutes)
        token = elevenlabs_client.tokens.single_use.create("realtime_scribe")
        return jsonify(token)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
    
    # Build transcription chain message
    transcription_chain = []
    if ELEVENLABS_API_KEY:
        transcription_chain.append("ElevenLabs Scribe")
    if DEEPGRAM_API_KEY:
        transcription_chain.append("Deepgram")
    if GROQ_API_KEY:
        transcription_chain.append("Groq")
    
    if transcription_chain:
        print(f"✓ Transcription Support: {' → '.join(transcription_chain)} (w/ Speaker Diarization)")
    else:
        print("✗ Transcription Support: No providers configured")
    
    print("✓ Distillation Support: enabled (Groq + Deepgram fallback)")
    
    if not ELEVENLABS_API_KEY and not DEEPGRAM_API_KEY and not GROQ_API_KEY:
        print("\n❌ CRITICAL: No transcription providers configured.")
    elif ELEVENLABS_API_KEY:
        print("\n✅ All systems ready (ElevenLabs Scribe primary - Premium quality)")
    elif DEEPGRAM_API_KEY:
        print("\n✅ Systems ready (Deepgram primary - Speaker diarization enabled)")
    else:
        print("\n⚠️  Running in Basic Mode (Groq only - no speaker diarization)")
    
    print("="*60 + "\n")
    
    app.run(debug=True, port=5000)

# For Vercel
app = app
