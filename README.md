# Briefly | Intelligent Signal Processing 🎯

**Intelligent Conversation Processing: Convert complex voice and chat signals into one-line intelligence.**

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/prathamamritkar/customer-convey-condense)

## 🚀 Quick Start (Milestone 1: Setup & Transcription)

### Local Node Initialization
```bash
# Install dependencies
pip install -r requirements.txt

# Start Signal Hub
python app.py

# Access Interface
# http://localhost:5000
```

### Vercel Cloud Deployment
1. **Push to GitHub**: Connect your repository to Vercel.
2. **Configure Environment**: 
   - Go to **Project Settings > Environment Variables** in the Vercel Dashboard.
   - Add `GROQ_API_KEY`: [Your Groq API Key]
3. **Deploy**: Trigger a new deployment.

## 🛠️ Performance Architecture

| Objective | Logic | Model |
|-----------|-------|-------|
| **Signal Decoding** | Voice to Text (STT) | Whisper-Large-V3 (via Groq) |
| **Logic Distillation**| Summarization | Llama-3.3-70B (via Groq) |

## 🧬 Core Logic (Milestone 1)

1. **Process Chats**: Directly ingest raw interaction logs or text.
2. **Convert Calls (STT)**: Decodes multi-format audio (.mp3, .wav, .m4a) into clean text streams.
3. **Summarization**: Generates a precise, one-line intelligence report from the provided data.
4. **Archive**: Persistent local storage for session-based history tracking.

## 📁 Repository Structure

```
app.py          # Backend Signal Node (Flask)
index.html      # Briefly Frontend UI
style.css       # Design System (8px Grid / M3 Logic)
script.js       # Orchestration & Logic
vercel.json     # Deployment Manifest
```

## 🔐 Configuration (Strict Mode)

This platform requires a **Groq API Key** for operation. 
1. Obtain a key at [console.groq.com](https://console.groq.com).
2. For local use: Create a `.env` file with `GROQ_API_KEY=your_key`.
3. For Cloud: Set the environment variable in your Vercel/Hosting dashboard.

**Note**: Internal fallbacks (mock data) are disabled to ensure production-grade data integrity.

## 📝 License

MIT | **Briefly: Distilling Clarity from Noise.**
