"""
Briefly — Provider Diagnostic Script
=====================================
Tests every transcription provider independently against real audio files.
Run with:  C:\Python314\python.exe test_providers.py

Reads API keys from .env automatically.
"""

import os
import sys
import json
import traceback
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Test audio files ──────────────────────────────────────────────────────────
DATASETS_DIR = Path(__file__).parent / "datasets"
TEST_FILES   = [
    DATASETS_DIR / "call log 1.m4a",
    DATASETS_DIR / "call log 2.m4a",
]

GROQ_API_KEY       = os.getenv("GROQ_API_KEY", "")
DEEPGRAM_API_KEY   = os.getenv("DEEPGRAM_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")

PASS = "✅ PASS"
FAIL = "❌ FAIL"
SKIP = "⏭  SKIP"

# ─────────────────────────────────────────────────────────────────────────────
def header(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")

def result_box(label, status, detail=""):
    print(f"  {status}  {label}")
    if detail:
        # indent multi-line detail
        for line in str(detail)[:800].splitlines():
            print(f"         {line}")

# ─────────────────────────────────────────────────────────────────────────────
# PROVIDER 1 — ElevenLabs (newest SDK: .speech_to_text.convert)
# ─────────────────────────────────────────────────────────────────────────────
def test_elevenlabs(audio_path):
    header(f"ElevenLabs Speech-to-Text  [{audio_path.name}]")

    if not ELEVENLABS_API_KEY:
        result_box("ElevenLabs", SKIP, "ELEVENLABS_API_KEY not set")
        return

    from elevenlabs.client import ElevenLabs
    client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

    # ── Test A: .speech_to_text.convert (current SDK ≥ 1.x)
    print("\n  [A] Trying client.speech_to_text.convert(model_id='scribe_v1') ...", flush=True)
    try:
        with open(audio_path, "rb") as f:
            response = client.speech_to_text.convert(
                audio=f,
                model_id="scribe_v1",
                diarize=True,
                language_code="en",
            )
        _inspect_el_response(response, "A")
    except AttributeError as e:
        result_box("A: speech_to_text.convert", FAIL, f"AttributeError: {e}")
    except Exception as e:
        result_box("A: speech_to_text.convert", FAIL, traceback.format_exc())

    # ── Test B: .scribe.transcribe (legacy SDK path)
    print("\n  [B] Trying client.scribe.transcribe(model='scribe_v1') ...", flush=True)
    try:
        with open(audio_path, "rb") as f:
            response = client.scribe.transcribe(
                audio=f,
                model="scribe_v1",
                language="en",
                diarize=True,
            )
        _inspect_el_response(response, "B")
    except AttributeError as e:
        result_box("B: scribe.transcribe", FAIL, f"AttributeError: {e}")
    except Exception as e:
        result_box("B: scribe.transcribe", FAIL, traceback.format_exc())

    # ── Test C: show available top-level attributes on the client
    print("\n  [C] ElevenLabs client attributes (find the correct STT method):")
    attrs = [a for a in dir(client) if not a.startswith("_")]
    print(f"         {attrs}")


def _inspect_el_response(response, label):
    attrs = [a for a in dir(response) if not a.startswith("_")]
    print(f"         Response attrs: {attrs[:30]}")

    has_words    = hasattr(response, "words")    and bool(getattr(response, "words",    None))
    has_segments = hasattr(response, "segments") and bool(getattr(response, "segments", None))
    has_utterances = hasattr(response, "utterances") and bool(getattr(response, "utterances", None))
    has_text     = hasattr(response, "text")     and bool(getattr(response, "text",     None))

    print(f"         has_words={has_words}  has_segments={has_segments}  "
          f"has_utterances={has_utterances}  has_text={has_text}")

    if has_words:
        words = getattr(response, "words")
        first = words[0] if words else None
        if first:
            w_attrs = [a for a in dir(first) if not a.startswith("_")]
            print(f"         Word[0] attrs: {w_attrs}")
            spk = getattr(first, "speaker_id", None) or getattr(first, "speaker", None)
            print(f"         Word[0] speaker_id/speaker = {spk!r}")
        result_box(f"{label}: response.words ({len(words)} words)", PASS,
                   f"First 3 words: {[getattr(w,'text','?') for w in words[:3]]}")
    elif has_segments:
        segs = getattr(response, "segments")
        result_box(f"{label}: response.segments ({len(segs)} segs)", PASS,
                   f"Seg[0] = {segs[0]}")
    elif has_utterances:
        utts = getattr(response, "utterances")
        result_box(f"{label}: response.utterances ({len(utts)} utts)", PASS,
                   f"Utt[0] = {utts[0]}")
    elif has_text:
        txt = getattr(response, "text","")
        result_box(f"{label}: plain text (NO DIARIZATION)", FAIL,
                   f"Text: {txt[:200]}")
    else:
        result_box(f"{label}: unrecognised response", FAIL, str(response)[:300])


# ─────────────────────────────────────────────────────────────────────────────
# PROVIDER 2 — Deepgram Nova-2
# ─────────────────────────────────────────────────────────────────────────────
def test_deepgram(audio_path):
    header(f"Deepgram Nova-2  [{audio_path.name}]")

    if not DEEPGRAM_API_KEY:
        result_box("Deepgram", SKIP, "DEEPGRAM_API_KEY not set")
        return

    from deepgram import DeepgramClient

    # ── Find PrerecordedOptions ──────────────────────────────────────────────
    PrerecordedOptions = None

    # Path A: root import (SDK v3)
    try:
        from deepgram import PrerecordedOptions as PRO
        PrerecordedOptions = PRO
        result_box("PrerecordedOptions import (root)", PASS)
    except ImportError as e:
        result_box("PrerecordedOptions import (root)", FAIL, str(e))

    # Path B: sub-module (SDK v6+)
    if PrerecordedOptions is None:
        try:
            from deepgram.audio.transcribe import PrerecordedOptions as PRO2
            PrerecordedOptions = PRO2
            result_box("PrerecordedOptions import (deepgram.audio.transcribe)", PASS)
        except ImportError as e:
            result_box("PrerecordedOptions import (deepgram.audio.transcribe)", FAIL, str(e))

    # Path C: dict-based options (no class needed — works in ALL SDK versions)
    print("\n  [A] Trying dict-based options (SDK-version-agnostic) ...", flush=True)
    client = DeepgramClient(api_key=DEEPGRAM_API_KEY)
    try:
        with open(audio_path, "rb") as f:
            buf = f.read()

        options_dict = {
            "model":        "nova-2",
            "smart_format": True,
            "diarize":      True,
            "punctuate":    True,
            "utterances":   True,
            "language":     "en",
        }

        response = client.listen.prerecorded.v("1").transcribe_file(
            {"buffer": buf},
            options_dict,
        )
        _inspect_dg_response(response, "A dict-options")
    except Exception as e:
        result_box("A: dict-options transcribe_file", FAIL, traceback.format_exc())

    # Path D: if PrerecordedOptions class found, use it
    if PrerecordedOptions is not None:
        print("\n  [B] Trying PrerecordedOptions class ...", flush=True)
        try:
            with open(audio_path, "rb") as f:
                buf = f.read()
            opts = PrerecordedOptions(
                model="nova-2", smart_format=True,
                diarize=True, punctuate=True,
                utterances=True, language="en",
            )
            response = client.listen.prerecorded.v("1").transcribe_file(
                {"buffer": buf}, opts
            )
            _inspect_dg_response(response, "B PrerecordedOptions")
        except Exception as e:
            result_box("B: PrerecordedOptions", FAIL, traceback.format_exc())

    # Show deepgram module structure
    import deepgram as dg_mod
    print(f"\n  [INFO] deepgram package version: {getattr(dg_mod, '__version__', 'unknown')}")
    print(f"  [INFO] deepgram top-level exports: {[x for x in dir(dg_mod) if not x.startswith('_')][:20]}")


def _inspect_dg_response(response, label):
    has_results = hasattr(response, "results") and response.results is not None
    if not has_results:
        result_box(label, FAIL, f"response.results is None/missing. Raw: {str(response)[:300]}")
        return

    r = response.results
    has_utterances = hasattr(r, "utterances") and r.utterances
    has_channels   = hasattr(r, "channels")   and r.channels

    if has_utterances:
        utts = r.utterances
        speakers = set(u.speaker for u in utts)
        sample = f"Speaker {utts[0].speaker}: {utts[0].transcript[:80]}"
        result_box(f"{label} — utterances", PASS,
                   f"{len(utts)} utterances, {len(speakers)} speakers\n{sample}")
    elif has_channels and r.channels:
        alt = r.channels[0].alternatives[0]
        result_box(f"{label} — plain (NO DIARIZATION)", FAIL,
                   f"Transcript: {alt.transcript[:200]}")
    else:
        result_box(label, FAIL, f"Unrecognised structure: {dir(r)}")


# ─────────────────────────────────────────────────────────────────────────────
# PROVIDER 3 — Groq Whisper
# ─────────────────────────────────────────────────────────────────────────────
def test_groq(audio_path):
    header(f"Groq Whisper-large-v3  [{audio_path.name}]")

    if not GROQ_API_KEY:
        result_box("Groq", SKIP, "GROQ_API_KEY not set")
        return

    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)

    try:
        with open(audio_path, "rb") as f:
            t = client.audio.transcriptions.create(
                file=(audio_path.name, f.read()),
                model="whisper-large-v3",
                response_format="verbose_json",
                language="en",
                temperature=0.0,
            )
        text = getattr(t, "text", str(t))
        result_box("Groq transcription (no diarization — expected)", PASS,
                   f"Text: {text[:300]}")
    except Exception as e:
        result_box("Groq transcription", FAIL, traceback.format_exc())


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n🔬  BRIEFLY — PROVIDER DIAGNOSTIC")
    print(f"    Python: {sys.version}")
    print(f"    Keys loaded: EL={'yes' if ELEVENLABS_API_KEY else 'NO'}  "
          f"DG={'yes' if DEEPGRAM_API_KEY else 'NO'}  "
          f"GQ={'yes' if GROQ_API_KEY else 'NO'}")
    print(f"    Test files: {[f.name for f in TEST_FILES if f.exists()]}")

    # Use first available test file
    audio = next((f for f in TEST_FILES if f.exists()), None)
    if audio is None:
        print("\n❌  No audio test files found in datasets/. Exiting.")
        sys.exit(1)

    test_elevenlabs(audio)
    test_deepgram(audio)
    test_groq(audio)

    print("\n" + "="*60)
    print("  DIAGNOSTIC COMPLETE")
    print("="*60 + "\n")
