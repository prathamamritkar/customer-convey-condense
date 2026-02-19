/* ========================================================================
   CONVEY — CORE LOGIC V2
   Architecture: Clean, Modular, State-Driven
   ======================================================================== */

// ── Configuration ───────────────────────────────────────────────────────
const API_BASE_URL = window.location.hostname === 'localhost'
    ? 'http://localhost:5000/api'
    : '/api';

// ── Application State ────────────────────────────────────────────────────
// ── Defensive Persistence ────────────────────────────────────────────────
let savedHistory = [];
try {
    // Attempt migration from legacy key if new key doesn't exist
    let raw = localStorage.getItem('briefly_history');
    if (!raw) {
        raw = localStorage.getItem('ccc_history');
        if (raw) localStorage.setItem('briefly_history', raw);
    }

    if (raw) savedHistory = JSON.parse(raw);
    if (!Array.isArray(savedHistory)) savedHistory = [];
} catch (e) {
    console.error("Archive corruption detected, resetting buffer.", e);
}

const AppState = {
    chatDoc: null,
    currentAudio: null,
    history: savedHistory,
    activeView: 'chat',
    mediaRecorder: null,
    audioChunks: [],
    isRecording: false,
    isProcessing: false,
};

// ── DOM Orchestration ────────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const UI = {
    navTabs: $$('.nav-tab'),
    panels: {
        chat: $('#panel-chat'),
        call: $('#panel-call'),
        history: $('#panel-history'),
        results: $('#panel-results'),
    },
    chat: {
        input: $('#chat-input'),
        submitBtn: $('#process-chat-btn'),
        fileInput: $('#chat-file-input'),
        dropzone: $('#chat-dropzone'),
        chip: $('#chat-file-chip'),
        fileName: $('#chat-file-name'),
        removeBtn: $('#chat-remove-file'),
    },
    audio: {
        fileInput: $('#audio-input'),
        dropzone: $('#dropzone'),
        chip: $('#file-chip'),
        fileName: $('#file-name'),
        removeBtn: $('#remove-file'),
        submitBtn: $('#process-call-btn'),
        micBtn: $('#mic-record-btn'),
        micText: $('#mic-text'),
    },
    results: {
        badge: $('#result-badge'),
        summary: $('#summary-text'),
        transBlock: $('#transcription-block'),
        transText: $('#transcription-text'),
        origBlock: $('#original-block'),
        origText: $('#original-text'),
        copyBtn: $('#copy-btn'),
        backBtn: $('#back-btn'),
    },
    historyList: $('#history-list'),
    overlayLoader: $('#loader'),
    loaderText: $('#loader-text'),
    infoBar: $('#app-status-bar'),
    toastOutlet: $('#toast-outlet'),
};

// ── Interactivity Layer ──────────────────────────────────────────────────

/**
 * Synchronizes UI interactive elements with current processing states.
 */
function syncInteractiveState() {
    const hasChatContent = UI.chat.input.value.trim().length > 0;
    UI.chat.submitBtn.disabled = AppState.isProcessing || AppState.isRecording || (!hasChatContent && !AppState.chatDoc);
    UI.audio.submitBtn.disabled = AppState.isProcessing || AppState.isRecording || !AppState.currentAudio;
}

/**
 * Global UI Lock during intensive async operations.
 */
function setGlobalLock(lock) {
    AppState.isProcessing = lock;

    [UI.chat.submitBtn, UI.audio.submitBtn, UI.chat.removeBtn, UI.audio.removeBtn].forEach(el => {
        if (el) el.disabled = lock;
    });

    UI.navTabs.forEach(tab => {
        tab.style.pointerEvents = lock ? 'none' : 'auto';
        tab.style.opacity = lock ? '0.4' : '1';
    });

    UI.chat.input.disabled = lock || !!AppState.chatDoc;
    syncInteractiveState();
}

/**
 * View Router - Handles tab switching and view consistency.
 */
function navigateTo(viewName) {
    if (AppState.isProcessing || AppState.isRecording) return;

    AppState.activeView = viewName;

    UI.navTabs.forEach(tab => {
        const isActive = tab.dataset.tab === viewName;
        tab.classList.toggle('active', isActive);
        tab.setAttribute('aria-selected', isActive);
    });

    Object.values(UI.panels).forEach(panel => {
        panel.classList.remove('active');
        panel.hidden = true;
    });

    const target = UI.panels[viewName];
    if (target) {
        target.hidden = false;
        target.classList.add('active');
    }

    if (viewName === 'history') renderArchive();
}

// ── Event Engineering ────────────────────────────────────────────────────

// Keyboard & Navigation
UI.navTabs.forEach(tab => tab.addEventListener('click', () => navigateTo(tab.dataset.tab)));
UI.chat.input.addEventListener('input', () => {
    syncInteractiveState();
    UI.chat.input.style.height = 'auto';
    UI.chat.input.style.height = Math.min(UI.chat.input.scrollHeight, 300) + 'px';
});
UI.chat.input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.ctrlKey) {
        e.preventDefault();
        UI.chat.submitBtn.click();
    }
});

// File Handling (Chat/Docs)
UI.chat.dropzone.addEventListener('click', () => !AppState.isProcessing && UI.chat.fileInput.click());
UI.chat.fileInput.addEventListener('change', (e) => e.target.files.length && handleChatFile(e.target.files[0]));
UI.chat.removeBtn.addEventListener('click', () => resetChatInput());

function handleChatFile(file) {
    const validExts = ['.txt', '.csv', '.json', '.md', '.log', '.pdf'];
    if (!validExts.some(ext => file.name.toLowerCase().endsWith(ext))) {
        return notify('Format not supported. Use PDF, TXT, CSV, or MD.', 'error');
    }

    AppState.chatDoc = file;
    UI.chat.fileName.textContent = file.name;
    UI.chat.dropzone.hidden = true;
    UI.chat.chip.hidden = false;
    UI.chat.input.disabled = true;
    UI.chat.input.placeholder = "Document loaded. System ready.";
    syncInteractiveState();
}

function resetChatInput() {
    AppState.chatDoc = null;
    UI.chat.fileInput.value = '';
    UI.chat.dropzone.hidden = false;
    UI.chat.chip.hidden = true;
    UI.chat.input.disabled = false;
    UI.chat.input.placeholder = "Paste raw text or interaction logs here...";
    syncInteractiveState();
}

// File Handling (Audio)
UI.audio.dropzone.addEventListener('click', () => !AppState.isProcessing && UI.audio.fileInput.click());
UI.audio.fileInput.addEventListener('change', (e) => e.target.files.length && handleAudioFile(e.target.files[0]));
UI.audio.removeBtn.addEventListener('click', () => resetAudioInput());

function handleAudioFile(file) {
    const validExts = ['.mp3', '.wav', '.m4a', '.ogg', '.webm', '.mp4'];
    if (!validExts.some(ext => file.name.toLowerCase().endsWith(ext))) {
        return notify('Incompatible audio format.', 'error');
    }
    if (file.size > 50 * 1024 * 1024) return notify('File exceeds 50MB high-capacity threshold.', 'error');

    AppState.currentAudio = file;
    UI.audio.fileName.textContent = file.name;
    UI.audio.dropzone.hidden = true;
    UI.audio.chip.hidden = false;
    syncInteractiveState();
}

function resetAudioInput() {
    AppState.currentAudio = null;
    UI.audio.fileInput.value = '';
    UI.audio.dropzone.hidden = false;
    UI.audio.chip.hidden = true;
    syncInteractiveState();
}

// ── Intelligence Processing ──────────────────────────────────────────────

UI.chat.submitBtn.addEventListener('click', async () => {
    if (AppState.chatDoc) await processTextDocument();
    else await processRawText();
});

UI.audio.submitBtn.addEventListener('click', async () => await processVoiceSignal());

async function processRawText() {
    const text = UI.chat.input.value.trim();
    if (!text) return;

    toggleLoader(true, 'Processing signal...');
    setGlobalLock(true);
    try {
        const res = await apiFetch('/process-chat', {
            method: 'POST',
            body: JSON.stringify({ text }),
            headers: { 'Content-Type': 'application/json' }
        });
        displayReport(res);
        archiveDistillation(res);
    } catch (err) {
        notify(err.message, 'error');
    } finally {
        toggleLoader(false);
        setGlobalLock(false);
    }
}

async function processTextDocument() {
    toggleLoader(true, 'Analyzing raw source...');
    setGlobalLock(true);
    try {
        const formData = new FormData();
        formData.append('file', AppState.chatDoc);
        const res = await apiFetch('/process-file', {
            method: 'POST',
            body: formData
        });
        displayReport(res);
        archiveDistillation(res);
        resetChatInput();
    } catch (err) {
        notify(err.message, 'error');
    } finally {
        toggleLoader(false);
        setGlobalLock(false);
    }
}

async function processVoiceSignal() {
    toggleLoader(true, 'Converting voice to text...');
    setGlobalLock(true);
    try {
        const formData = new FormData();
        formData.append('audio', AppState.currentAudio);
        const res = await apiFetch('/process-call', {
            method: 'POST',
            body: formData
        });
        displayReport(res);
        archiveDistillation(res);
        resetAudioInput();
    } catch (err) {
        notify(err.message, 'error');
    } finally {
        toggleLoader(false);
        setGlobalLock(false);
    }
}

// ── Recording Engineering ────────────────────────────────────────────────

UI.audio.micBtn.addEventListener('click', () => {
    if (AppState.isProcessing) return;
    if (AppState.isRecording) finalizeRecording();
    else initiateRecording();
});

async function initiateRecording() {
    if (!navigator.mediaDevices || !window.MediaRecorder) {
        return notify('Capture system not compatible with this environment.', 'error');
    }

    AppState.audioChunks = [];
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        AppState.mediaRecorder = new MediaRecorder(stream);

        AppState.mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) AppState.audioChunks.push(e.data);
        };

        AppState.mediaRecorder.onstop = () => {
            const blob = new Blob(AppState.audioChunks, { type: 'audio/wav' });
            handleAudioFile(new File([blob], 'capture.wav', { type: 'audio/wav' }));
            stream.getTracks().forEach(t => t.stop());
            setGlobalLock(false);
        };

        AppState.mediaRecorder.start();
        AppState.isRecording = true;
        setGlobalLock(true);
        AppState.isProcessing = false;

        UI.audio.micBtn.classList.add('recording');
        UI.audio.micBtn.disabled = false;
        UI.audio.micText.textContent = 'Recording Active (Click to Stop)';
        notify('Voice capture active', 'success');
    } catch (e) {
        notify('Microphone authentication failed', 'error');
    }
}

function finalizeRecording() {
    if (AppState.mediaRecorder && AppState.isRecording) {
        AppState.mediaRecorder.stop();
        AppState.isRecording = false;
        UI.audio.micBtn.classList.remove('recording');
        UI.audio.micText.textContent = 'Capture Live Audio';
    }
}

// ── Distillation Reporting ───────────────────────────────────────────────

function displayReport(data) {
    UI.results.badge.textContent = data.type === 'chat' ? 'Text Insight' : 'Voice Insight';
    UI.results.summary.textContent = data.summary;

    const showTranscription = data.type === 'call' && data.transcription;
    UI.results.transBlock.hidden = !showTranscription;
    if (showTranscription) UI.results.transText.textContent = data.transcription;

    const showSource = data.type === 'chat' && data.original_text;
    UI.results.origBlock.hidden = !showSource;
    if (showSource) UI.results.origText.textContent = data.original_text;

    Object.values(UI.panels).forEach(p => { p.classList.remove('active'); p.hidden = true; });
    UI.panels.results.hidden = false;
    UI.panels.results.classList.add('active');
    notify('Meaning distilled', 'success');
}

UI.results.backBtn.addEventListener('click', () => navigateTo(AppState.activeView));
UI.results.copyBtn.addEventListener('click', () => {
    navigator.clipboard.writeText(UI.results.summary.textContent).then(() => notify('Report copied to clipboard', 'success'));
});

// ── Archive & History ───────────────────────────────────────────────────

function archiveDistillation(data) {
    AppState.history.unshift({
        id: Date.now(),
        type: data.type,
        summary: data.summary,
        transcription: data.transcription || null,
        original_text: data.original_text || null,
        timestamp: data.timestamp || new Date().toISOString(),
    });
    if (AppState.history.length > 50) AppState.history = AppState.history.slice(0, 50);
    localStorage.setItem('briefly_history', JSON.stringify(AppState.history));
}

function renderArchive() {
    if (!AppState.history.length) {
        UI.historyList.innerHTML = `
            <div class="empty-state" style="text-align: center; padding: var(--s8) 0; opacity: 0.5;">
                <p>Archive Empty</p>
                <p style="font-size: 0.8rem;">Your past distillations will be saved here.</p>
            </div>`;
        return;
    }

    UI.historyList.innerHTML = AppState.history.map(item => `
        <div class="history-card" data-id="${item.id}">
            <div class="history-header">
                <span class="item-type">${item.type === 'chat' ? 'TEXT' : 'VOICE'}</span>
                <span class="item-time">${formatTimeAgo(new Date(item.timestamp))}</span>
            </div>
            <div class="item-preview">${item.summary}</div>
        </div>
    `).join('');

    $$('.history-card').forEach(card => {
        card.addEventListener('click', () => {
            if (AppState.isProcessing || AppState.isRecording) return;
            const entry = AppState.history.find(h => h.id === parseInt(card.dataset.id));
            if (entry) displayReport(entry);
        });
    });
}

// ── Utilities & Infrastructure ──────────────────────────────────────────

async function apiFetch(path, options = {}) {
    const res = await fetch(`${API_BASE_URL}${path}`, options);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Distillation failed.');
    return data;
}

function toggleLoader(visible, msg = '') {
    UI.loaderText.textContent = msg;
    UI.overlayLoader.hidden = !visible;
}

function notify(msg, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `modern-toast ${type}`;
    toast.textContent = msg;
    UI.toastOutlet.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(20px)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function formatTimeAgo(date) {
    const s = Math.floor((Date.now() - date.getTime()) / 1000);
    if (s < 0) return 'Just now';
    if (s < 10) return 'Just now';
    if (s < 60) return `${s}s ago`;
    const units = [['yr', 31536000], ['mo', 2592000], ['wk', 604800], ['d', 86400], ['hr', 3600], ['m', 60]];
    for (const [u, secs] of units) {
        const n = Math.floor(s / secs);
        if (n >= 1) return `${n}${u} ago`;
    }
    return 'Just now';
}

async function verifyConnection() {
    try {
        const res = await fetch(`${API_BASE_URL}/health`);
        const data = await res.json();
        UI.infoBar.classList.remove('status-offline');

        const statusText = $('#status-text');
        if (data.api_ready) {
            statusText.textContent = 'Briefly Node: Active';
        } else if (data.fallbacks && data.fallbacks.deepgram) {
            statusText.textContent = 'Briefly Node: Fallback Mode';
        } else {
            statusText.textContent = 'API Node: Restricted';
        }
    } catch {
        UI.infoBar.classList.add('status-offline');
        $('#status-text').textContent = 'Global Node: Offline';
    }
}

// ── System Initialization ───────────────────────────────────────────────
syncInteractiveState();
verifyConnection();
setInterval(verifyConnection, 30000);
