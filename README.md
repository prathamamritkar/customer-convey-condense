# Customer Convey Condense 🎯

**AI-powered customer communication summarizer. Works locally AND on Vercel. 100% FREE.**

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/yourusername/customer-convey-condense)

## 🚀 Quick Start

### Local (Heavy Models - Offline)
```bash
# Install
pip install -r requirements.txt

# Run
python app.py

# Open http://localhost:5000
```

### Vercel (Cloud APIs - Online)
```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel

# Add secrets
vercel env add DEEPGRAM_API_KEY
vercel env add GROQ_API_KEY
```

## 💰 Cost: $0.00/month

| Mode | STT | Summarization | Cost |
|------|-----|---------------|------|
| **Local** | Whisper (offline) | BART (offline) | FREE |
| **Vercel** | Deepgram API | Groq API | FREE |

## 🎯 Features

- ✅ Transcribe audio calls (MP3, WAV, M4A)
- ✅ Summarize chat conversations
- ✅ Beautiful dark UI with glassmorphism
- ✅ History tracking (localStorage)
- ✅ Drag & drop file upload
- ✅ Works offline (local mode)
- ✅ Deploy to Vercel in 1 click

## 📁 Structure

```
app.py          # Smart routing: local models OR cloud APIs
index.html      # Frontend UI
style.css       # Premium dark theme
script.js       # Frontend logic
vercel.json     # Vercel config
```

## 🔑 API Keys (FREE)

### Deepgram (Speech-to-Text)
1. Sign up: https://deepgram.com
2. Get API key (FREE tier: 45,000 minutes/year)
3. Already provided: `4628aa09105589ba57d6f9d84e0c4b7189d02df6`

### Groq (Summarization)
1. Sign up: https://console.groq.com
2. Get API key (FREE tier: unlimited)
3. Add to `.env`: `GROQ_API_KEY=your_key_here`

## 🛠️ How It Works

### Local Mode
```
Audio → Whisper (local) → Text → BART (local) → Summary
```

### Vercel Mode
```
Audio → Deepgram API → Text → Groq API → Summary
```

**Smart routing**: Automatically uses local models if available, falls back to cloud APIs.

## 📊 API Endpoints

```bash
POST /api/process-chat
POST /api/process-call
GET  /api/health
```

## 🎨 UI

- Dark theme with purple/blue gradients
- Glassmorphism effects
- Smooth animations
- Fully responsive
- Drag & drop support

## 🔒 Privacy

- **Local mode**: 100% offline, data never leaves your machine
- **Vercel mode**: Uses cloud APIs (Deepgram, Groq)

## 📝 License

MIT

---

**Built for hackathons. Ships fast. Works everywhere.**
