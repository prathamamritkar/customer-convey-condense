import os
import time
import json
import requests
import argparse
import sys
import wave
import struct
import math

# --- Utilities to create sample files ---
def create_sample_audio(filename="sample.wav", duration=2.0, sample_rate=16000):
    """Generates a simple sine wave audio file to test ASR/acoustic processing."""
    print(f"Generating sample audio: {filename}")
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        
        freq = 440.0 # A4 note
        n_samples = int(duration * sample_rate)
        for i in range(n_samples):
            t = float(i) / sample_rate
            value = int(32767.0 * math.sin(2.0 * math.pi * freq * t))
            data = struct.pack('<h', value)
            wav_file.writeframesraw(data)

def create_sample_text(filename="sample.txt"):
    """Generates a dummy text file."""
    print(f"Generating sample text file: {filename}")
    with open(filename, 'w') as f:
        f.write("SPEAKER_00: Hello, how can I help you today?\n")
        f.write("SPEAKER_01: My account is locked and I am very angry. Fix it immediately.\n")
        f.write("SPEAKER_00: I understand you are frustrated. Let me check your account details to help resolve this.")

def assert_success(condition, message):
    if not condition:
        print(f"❌ FAILED: {message}")
        sys.exit(1)
    print(f"✅ PASSED: {message}")

# --- Test Definitions ---

def test_health(base_url):
    print("\n--- Testing /api/health ---")
    res = requests.get(f"{base_url}/api/health")
    assert_success(res.status_code == 200, "Health endpoint returned 200")
    data = res.json()
    assert_success(data.get('status') == 'operational', "Status is operational")
    print(json.dumps(data, indent=2))

def test_process_chat(base_url):
    print("\n--- Testing /api/process-chat ---")
    payload = {"text": "Agent: Hi, how can I help? Customer: The app keeps crashing when I open settings. Agent: I'm sorry to hear that. Have you tried reinstalling it?"}
    res = requests.post(f"{base_url}/api/process-chat", json=payload)
    assert_success(res.status_code == 200, "Process-chat endpoint returned 200")
    data = res.json()
    assert_success(data.get('success'), "Audit was successful")
    assert_success('audit' in data, "Audit content present")
    print("Chat Audit F1:", data['audit'].get('agent_f1_score'))

def test_process_file(base_url):
    print("\n--- Testing /api/process-file ---")
    create_sample_text("test_audit.txt")
    with open("test_audit.txt", "rb") as f:
        files = {"file": ("test_audit.txt", f, "text/plain")}
        res = requests.post(f"{base_url}/api/process-file", files=files)
        assert_success(res.status_code == 200, "Process-file endpoint returned 200")
        data = res.json()
        assert_success(data.get('success'), "File audit was successful")
        assert_success('audit' in data, "Audit content present")
        print("File Audit Summary:", data['audit'].get('summary'))
    os.remove("test_audit.txt")

def test_call_audit_flow(base_url):
    print("\n--- Testing Call Audit Flow (Upload -> Status Polling) ---")
    create_sample_audio("test_call.wav")
    
    # Upload Audio
    with open("test_call.wav", "rb") as f:
        files = {"audio": ("test_call.wav", f, "audio/wav")}
        res = requests.post(f"{base_url}/api/start-call-audit", files=files)
        assert_success(res.status_code == 200, "Start call audit returned 200")
        data = res.json()
        job_id = data.get('job_id')
        assert_success(job_id is not None, "Received job_id")
        fallbacks = data.get('fallbacks_available')
        print(f"Job ID: {job_id} | Fallbacks available: {fallbacks}")

    # Polling
    max_attempts = 150 # 5 minutes max
    attempt = 0
    poll_interval = 2
    
    while attempt < max_attempts:
        attempt += 1
        res = requests.get(f"{base_url}/api/job/{job_id}/status")
        assert_success(res.status_code == 200, f"Poll {attempt} returned 200")
        data = res.json()
        
        status = data.get('status')
        print(f"Status poll {attempt}: {status}")
        
        if status == 'done':
            assert_success('audit' in data, "Audit content present in final job data")
            assert_success('transcript' in data, "Transcript present in final job data")
            print(f"Source: {data.get('source')}")
            break
        elif status == 'error':
            assert_success(False, f"Job failed: {data.get('error')}")
            break
            
        time.sleep(poll_interval)
    
    if attempt >= max_attempts:
        assert_success(False, "Call audit polling timed out")

    os.remove("test_call.wav")

def test_fast_track_flow(base_url):
    print("\n--- Testing Call Audit Flow (Fast Track / Transcribe Now) ---")
    create_sample_audio("test_call_fast_track.wav")
    
    # Upload Audio
    with open("test_call_fast_track.wav", "rb") as f:
        files = {"audio": ("test_call_fast_track.wav", f, "audio/wav")}
        res = requests.post(f"{base_url}/api/start-call-audit", files=files)
        assert_success(res.status_code == 200, "Start call audit returned 200")
        data = res.json()
        job_id = data.get('job_id')
        assert_success(job_id is not None, "Received job_id")
        
    print(f"Triggering fast track for Job ID: {job_id}")
    res = requests.post(f"{base_url}/api/job/{job_id}/transcribe-now")
    assert_success(res.status_code == 200, "Fast track triggered successfully")
    data = res.json()
    assert_success(data.get('triggered') or data.get('message'), "Transcribe now responded properly")

    # Polling
    attempt = 0
    poll_interval = 2
    max_attempts = 150
    while attempt < max_attempts:
        attempt += 1
        res = requests.get(f"{base_url}/api/job/{job_id}/status")
        data = res.json()
        status = data.get('status')
        print(f"Status poll {attempt} (fast-tracked): {status}")
        
        if status == 'done':
            assert_success('audit' in data, "Audit content present in final job data")
            assert_success(data.get('api_chain_started'), "API chain was explicitly tracked as started")
            break
        elif status == 'error':
            assert_success(False, f"Job failed: {data.get('error')}")
            break
            
        time.sleep(poll_interval)
    
    os.remove("test_call_fast_track.wav")

def run_all(base_url):
    print(f"Starting E2E Tests on {base_url}\n")
    try:
        test_health(base_url)
        test_process_chat(base_url)
        test_process_file(base_url)
        test_call_audit_flow(base_url)
        test_fast_track_flow(base_url)
        print("\n🎉 ALL TESTS PASSED SUCCESSFULLY!")
    except Exception as e:
        print(f"\n❌ UNEXPECTED TEST EXCEPTION: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="End-to-End Tests for Qualora QA")
    parser.add_argument("--url", default="http://localhost:5000", help="Base URL of the server (e.g. http://127.0.0.1:5000 or https://your-vercel.app)")
    args = parser.parse_args()
    
    # Make sure server is reachable
    try:
        requests.get(f"{args.url}/api/health")
    except requests.exceptions.ConnectionError:
        print(f"❌ ERROR: Server at {args.url} is not unreachable. Please start the server first.")
        sys.exit(1)

    run_all(args.url)
