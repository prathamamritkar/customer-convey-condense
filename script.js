/* ========================================================================
   BRIEFLY QA — CORE LOGIC V3 (Milestone 2)
   Architecture: Audit-First, Chart-Driven, HITL-Ready
   ======================================================================== */

// ── Configuration ─────────────────────────────────────────────────────────
const API_BASE_URL = window.location.hostname === 'localhost'
    ? 'http://localhost:5000/api'
    : '/api';

// ── Global Chart References (for destroy/re-init) ─────────────────────────
let _radarChart = null;
let _echartsInstance = null;

// ── Persistent State ───────────────────────────────────────────────────────
let savedHistory = [];
try {
    let raw = localStorage.getItem('brieflyqa_history') || localStorage.getItem('briefly_history');
    if (raw) savedHistory = JSON.parse(raw);
    if (!Array.isArray(savedHistory)) savedHistory = [];
} catch (e) {
    console.error("Archive corruption detected, resetting.", e);
}

const AppState = {
    chatDoc: null,
    currentAudio: null,
    history: savedHistory,
    activeView: 'call',
    mediaRecorder: null,
    audioChunks: [],
    isRecording: false,
    isProcessing: false,
    lastAudit: null,
    hitlStatus: null,  // 'approved' | 'flagged' | 'rejected' | null
};

// ── DOM Shortcuts ──────────────────────────────────────────────────────────
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
        micIcon: $('#mic-icon-sym'),
    },
    results: {
        kpiF1: $('#kpi-f1-val'),
        kpiSat: $('#kpi-sat-val'),
        kpiComp: $('#kpi-comp-val'),
        kpiF1Card: $('#kpi-f1'),
        kpiCompCard: $('#kpi-compliance'),
        summary: $('#summary-text'),
        transBlock: $('#transcription-block'),
        transText: $('#transcription-text'),
        flagsList: $('#flags-list'),
        nudgesList: $('#nudges-list'),
        flagsSection: $('#flags-section'),
        copyBtn: $('#copy-btn'),
        backBtn: $('#back-btn'),
    },
    hitl: {
        panel: $('#hitl-panel'),
        badge: $('#hitl-badge'),
        approveBtn: $('#hitl-approve-btn'),
        flagBtn: $('#hitl-flag-btn'),
        rejectBtn: $('#hitl-reject-btn'),
        status: $('#hitl-status'),
    },
    historyList: $('#history-list'),
    overlayLoader: $('#loader'),
    loaderText: $('#loader-text'),
    infoBar: $('#app-status-bar'),
    toastOutlet: $('#toast-outlet'),
};

// ── Interactive State Sync ────────────────────────────────────────────────
function syncInteractiveState() {
    const hasChatContent = UI.chat.input.value.trim().length > 0;
    UI.chat.submitBtn.disabled = AppState.isProcessing || AppState.isRecording || (!hasChatContent && !AppState.chatDoc);
    UI.audio.submitBtn.disabled = AppState.isProcessing || AppState.isRecording || !AppState.currentAudio;
}

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

// ── View Router ───────────────────────────────────────────────────────────
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
    if (target) { target.hidden = false; target.classList.add('active'); }
    if (viewName === 'history') renderArchive();
}

// ── Navigation Events ──────────────────────────────────────────────────────
UI.navTabs.forEach(tab => tab.addEventListener('click', () => navigateTo(tab.dataset.tab)));

UI.chat.input.addEventListener('input', () => {
    syncInteractiveState();
    UI.chat.input.style.height = 'auto';
    UI.chat.input.style.height = Math.min(UI.chat.input.scrollHeight, 300) + 'px';
});
UI.chat.input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.ctrlKey) { e.preventDefault(); UI.chat.submitBtn.click(); }
});

// ── File Handling ──────────────────────────────────────────────────────────
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
    UI.chat.input.placeholder = "Document loaded. Ready to audit.";
    syncInteractiveState();
}

function resetChatInput() {
    AppState.chatDoc = null;
    UI.chat.fileInput.value = '';
    UI.chat.dropzone.hidden = false;
    UI.chat.chip.hidden = true;
    UI.chat.input.disabled = false;
    UI.chat.input.placeholder = "Or paste chat transcript directly here...";
    syncInteractiveState();
}

UI.audio.dropzone.addEventListener('click', () => !AppState.isProcessing && UI.audio.fileInput.click());
UI.audio.fileInput.addEventListener('change', (e) => e.target.files.length && handleAudioFile(e.target.files[0]));
UI.audio.removeBtn.addEventListener('click', () => resetAudioInput());

function handleAudioFile(file) {
    const validExts = ['.mp3', '.wav', '.m4a', '.ogg', '.webm', '.mp4'];
    if (!validExts.some(ext => file.name.toLowerCase().endsWith(ext))) {
        return notify('Incompatible audio format.', 'error');
    }
    if (file.size > 50 * 1024 * 1024) return notify('File exceeds 50MB limit.', 'error');
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

// ── Drag and Drop ──────────────────────────────────────────────────────────
[UI.audio.dropzone, UI.chat.dropzone].forEach(zone => {
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', e => {
        e.preventDefault();
        zone.classList.remove('drag-over');
        const file = e.dataTransfer.files[0];
        if (!file) return;
        if (zone === UI.audio.dropzone) handleAudioFile(file);
        else handleChatFile(file);
    });
});

// ── API Calls ──────────────────────────────────────────────────────────────
UI.chat.submitBtn.addEventListener('click', async () => {
    if (AppState.chatDoc) await processTextDocument();
    else await processRawText();
});
UI.audio.submitBtn.addEventListener('click', async () => await processVoiceSignal());

async function processRawText() {
    const text = UI.chat.input.value.trim();
    if (!text) return;
    toggleLoader(true, 'Auditing transcript with AI Judge...');
    setGlobalLock(true);
    try {
        const res = await apiFetch('/process-chat', {
            method: 'POST',
            body: JSON.stringify({ text }),
            headers: { 'Content-Type': 'application/json' }
        });
        renderAuditDashboard(res);
        archiveAudit(res);
    } catch (err) { notify(err.message, 'error'); }
    finally { toggleLoader(false); setGlobalLock(false); }
}

async function processTextDocument() {
    toggleLoader(true, 'Ingesting document...');
    setGlobalLock(true);
    try {
        const formData = new FormData();
        formData.append('file', AppState.chatDoc);
        const res = await apiFetch('/process-file', { method: 'POST', body: formData });
        renderAuditDashboard(res);
        archiveAudit(res);
        resetChatInput();
    } catch (err) { notify(err.message, 'error'); }
    finally { toggleLoader(false); setGlobalLock(false); }
}

async function processVoiceSignal() {
    toggleLoader(true, 'Transcribing call & running quality audit...');
    setGlobalLock(true);
    try {
        const formData = new FormData();
        formData.append('audio', AppState.currentAudio);
        const res = await apiFetch('/process-call', { method: 'POST', body: formData });
        renderAuditDashboard(res);
        archiveAudit(res);
        resetAudioInput();
    } catch (err) { notify(err.message, 'error'); }
    finally { toggleLoader(false); setGlobalLock(false); }
}

// ── Recording ─────────────────────────────────────────────────────────────
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
        AppState.mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) AppState.audioChunks.push(e.data); };
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
        UI.audio.micText.textContent = 'Recording Active — Click to Stop';
        UI.audio.micIcon.textContent = 'stop_circle';
        notify('Voice capture active', 'success');
    } catch (e) { notify('Microphone access denied.', 'error'); }
}

function finalizeRecording() {
    if (AppState.mediaRecorder && AppState.isRecording) {
        AppState.mediaRecorder.stop();
        AppState.isRecording = false;
        UI.audio.micBtn.classList.remove('recording');
        UI.audio.micText.textContent = 'Capture Live Audio';
        UI.audio.micIcon.textContent = 'mic';
    }
}

// ── AUDIT DASHBOARD RENDERER ──────────────────────────────────────────────
function renderAuditDashboard(data) {
    const audit = data.audit || {};
    AppState.lastAudit = audit;
    AppState.hitlStatus = null;

    // ── KPI Cards ────────────────────────────────────────────────────────
    const f1 = typeof audit.agent_f1_score === 'number' ? audit.agent_f1_score : null;
    UI.results.kpiF1.textContent = f1 !== null ? (f1 * 100).toFixed(0) + '%' : '—';
    UI.results.kpiF1Card.className = 'kpi-card ' + scoreClass(f1, [0.85, 0.65]);  // green/amber/red

    const sat = audit.satisfaction_prediction || '—';
    UI.results.kpiSat.textContent = sat;
    UI.results.kpiSat.closest('.kpi-card').className = 'kpi-card ' + satClass(sat);

    const risk = audit.compliance_risk || '—';
    UI.results.kpiComp.textContent = risk;
    UI.results.kpiCompCard.className = 'kpi-card ' + riskClass(risk);

    // ── Summary ──────────────────────────────────────────────────────────
    UI.results.summary.textContent = audit.summary || 'No summary available.';

    // ── Transcript (voice only) ───────────────────────────────────────────
    const hasTranscript = data.type === 'call' && data.transcription;
    UI.results.transBlock.open = false;
    UI.results.transBlock.hidden = !hasTranscript;
    if (hasTranscript) {
        UI.results.transText.innerHTML = formatTranscript(data.transcription);
    }

    // ── Compliance Flags ──────────────────────────────────────────────────
    const flags = Array.isArray(audit.compliance_flags) ? audit.compliance_flags : [];
    UI.results.flagsSection.hidden = false;
    if (flags.length === 0) {
        UI.results.flagsList.innerHTML = `<li class="detail-item no-issue"><span class="material-symbols-rounded">check_circle</span> No compliance issues detected</li>`;
    } else {
        UI.results.flagsList.innerHTML = flags.map(f =>
            `<li class="detail-item flag-item"><span class="material-symbols-rounded">warning</span>${escHtml(f)}</li>`
        ).join('');
    }

    // ── Behavioral Nudges ─────────────────────────────────────────────────
    const nudges = Array.isArray(audit.behavioral_nudges) ? audit.behavioral_nudges : [];
    UI.results.nudgesList.innerHTML = nudges.length
        ? nudges.map(n => `<li class="detail-item nudge-item"><span class="material-symbols-rounded">tips_and_updates</span>${escHtml(n)}</li>`).join('')
        : '<li class="detail-item">No nudges generated.</li>';

    // ── HITL Panel ────────────────────────────────────────────────────────
    UI.hitl.badge.textContent = 'AI Scored';
    UI.hitl.badge.className = 'hitl-badge';
    UI.hitl.status.hidden = true;
    if (audit.hitl_review_required) {
        UI.hitl.badge.textContent = 'Review Required';
        UI.hitl.badge.className = 'hitl-badge badge-warn';
        notify('Supervisor review recommended for this audit.', 'warning');
    }

    // ── Charts ────────────────────────────────────────────────────────────
    const qm = audit.quality_matrix || {};
    renderRadarChart(qm);

    const timeline = Array.isArray(audit.emotional_timeline) ? audit.emotional_timeline : [];
    renderEmotionTopography(timeline);

    // ── Show Dashboard ────────────────────────────────────────────────────
    Object.values(UI.panels).forEach(p => { p.classList.remove('active'); p.hidden = true; });
    UI.panels.results.hidden = false;
    UI.panels.results.classList.add('active');
    notify('Quality audit complete', 'success');
}

// ── CHART: 2D Agent Skill Radar (Chart.js) ────────────────────────────────
function renderRadarChart(qm) {
    if (_radarChart) { _radarChart.destroy(); _radarChart = null; }
    const ctx = document.getElementById('qualityRadarChart')?.getContext('2d');
    if (!ctx) return;

    const labels = ['Language\nProficiency', 'Cognitive\nEmpathy', 'Efficiency', 'Bias\nReduction', 'Active\nListening'];
    const values = [
        qm.language_proficiency || 0,
        qm.cognitive_empathy || 0,
        qm.efficiency || 0,
        qm.bias_reduction || 0,
        qm.active_listening || 0,
    ];

    _radarChart = new Chart(ctx, {
        type: 'radar',
        data: {
            labels,
            datasets: [{
                label: 'Agent Score',
                data: values,
                backgroundColor: 'rgba(99,102,241,0.2)',
                borderColor: 'rgba(99,102,241,0.9)',
                borderWidth: 2.5,
                pointBackgroundColor: 'rgba(99,102,241,1)',
                pointRadius: 5,
                pointHoverRadius: 7,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: ctx => ` ${ctx.raw}/10`
                    }
                }
            },
            scales: {
                r: {
                    beginAtZero: true,
                    max: 10,
                    ticks: {
                        stepSize: 2,
                        color: 'rgba(148,163,184,0.8)',
                        backdropColor: 'transparent',
                        font: { size: 10 }
                    },
                    grid: { color: 'rgba(148,163,184,0.15)' },
                    angleLines: { color: 'rgba(148,163,184,0.15)' },
                    pointLabels: {
                        color: '#CBD5E1',
                        font: { size: 11, family: 'Inter' }
                    }
                }
            }
        }
    });
}

// ── CHART: 3D Emotional Landscape Topography (Apache ECharts GL) ──────────
function renderEmotionTopography(timeline) {
    const container = document.getElementById('emotionTopographyChart');
    if (!container) return;

    if (_echartsInstance) { _echartsInstance.dispose(); _echartsInstance = null; }

    if (!timeline.length) {
        container.innerHTML = '<div class="chart-empty">No emotional timeline data available.</div>';
        return;
    }

    _echartsInstance = echarts.init(container);

    // Map emotions to numeric intensity values for Z-axis
    const emotionMap = {
        'Angry': -3, 'Frustrated': -2, 'Anxious': -1, 'Confused': -0.5,
        'Neutral': 0, 'Professional': 0.5,
        'Calm': 1, 'Empathetic': 1.5, 'Relieved': 2, 'Satisfied': 2.5, 'Happy': 3
    };

    // Build a 2D grid: X = turn index, Y = speaker (0=Customer, 1=Agent)
    const turns = timeline.length;
    const data = [];

    timeline.forEach((t, i) => {
        const yVal = t.speaker === 'Customer' ? 0 : 1;
        const zBase = emotionMap[t.emotion] ?? 0;
        const z = zBase + (t.intensity / 10) * 2; // scale intensity
        data.push([i, yVal, z]);
    });

    const option = {
        backgroundColor: 'transparent',
        tooltip: {
            formatter: params => {
                if (params.data) {
                    const turn = timeline[params.data[0]] || {};
                    return `Turn ${turn.turn || params.data[0] + 1}<br/>${turn.speaker}: <b>${turn.emotion}</b><br/>Intensity: ${turn.intensity}/10`;
                }
            }
        },
        grid3D: {
            boxWidth: 120,
            boxDepth: 40,
            boxHeight: 60,
            viewControl: {
                autoRotate: false,
                rotateSensitivity: 1.5,
                zoomSensitivity: 1.2,
                beta: 20,
                alpha: 25,
            },
            light: {
                main: { intensity: 1.5 },
                ambient: { intensity: 0.4 }
            },
            environment: 'none',
        },
        xAxis3D: {
            name: 'Call Turn',
            type: 'value',
            min: 0,
            max: turns,
            nameTextStyle: { color: '#94A3B8', fontSize: 11 },
            axisLabel: { color: '#94A3B8', fontSize: 9 },
            axisLine: { lineStyle: { color: '#334155' } },
            splitLine: { lineStyle: { color: 'rgba(148,163,184,0.1)' } },
        },
        yAxis3D: {
            name: 'Speaker',
            type: 'category',
            data: ['Customer', 'Agent'],
            nameTextStyle: { color: '#94A3B8', fontSize: 11 },
            axisLabel: { color: '#94A3B8', fontSize: 10 },
            axisLine: { lineStyle: { color: '#334155' } },
        },
        zAxis3D: {
            name: 'Emotional State',
            type: 'value',
            min: -4,
            max: 5,
            nameTextStyle: { color: '#94A3B8', fontSize: 11 },
            axisLabel: { color: '#94A3B8', fontSize: 9 },
            axisLine: { lineStyle: { color: '#334155' } },
            splitLine: { lineStyle: { color: 'rgba(148,163,184,0.1)' } },
        },
        visualMap: {
            show: true,
            dimension: 2,
            min: -4,
            max: 5,
            inRange: {
                color: ['#EF4444', '#F97316', '#EAB308', '#22C55E', '#6366F1']
            },
            textStyle: { color: '#94A3B8', fontSize: 9 },
            left: 'left',
            bottom: 10,
        },
        series: [{
            type: 'scatter3D',
            data,
            symbolSize: 14,
            itemStyle: {
                opacity: 0.9,
                borderColor: 'rgba(255,255,255,0.2)',
                borderWidth: 1,
            },
            emphasis: {
                itemStyle: { opacity: 1 },
                label: { show: false }
            }
        }]
    };

    _echartsInstance.setOption(option);

    // Resize on container resize
    const ro = new ResizeObserver(() => _echartsInstance && _echartsInstance.resize());
    ro.observe(container);
}

// ── HITL Actions ──────────────────────────────────────────────────────────
UI.hitl.approveBtn.addEventListener('click', () => handleHitl('approved', 'Audit approved by supervisor.', 'success'));
UI.hitl.flagBtn.addEventListener('click', () => handleHitl('flagged', 'Flagged for further review.', 'warning'));
UI.hitl.rejectBtn.addEventListener('click', () => handleHitl('rejected', 'Score rejected. Manual audit recommended.', 'error'));

function handleHitl(status, msg, type) {
    AppState.hitlStatus = status;
    UI.hitl.badge.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    UI.hitl.badge.className = 'hitl-badge ' + { approved: 'badge-green', flagged: 'badge-warn', rejected: 'badge-red' }[status];
    UI.hitl.status.hidden = false;
    UI.hitl.status.textContent = `Recorded: ${msg}`;
    UI.hitl.status.className = `hitl-status ${type}`;
    [UI.hitl.approveBtn, UI.hitl.flagBtn, UI.hitl.rejectBtn].forEach(b => b.disabled = true);
    notify(msg, type);
}

// ── Results Actions ───────────────────────────────────────────────────────
UI.results.backBtn.addEventListener('click', () => {
    if (_radarChart) { _radarChart.destroy(); _radarChart = null; }
    if (_echartsInstance) { _echartsInstance.dispose(); _echartsInstance = null; }
    navigateTo(AppState.activeView);
});

UI.results.copyBtn.addEventListener('click', () => {
    const audit = AppState.lastAudit;
    if (!audit) return;
    const text = [
        `Summary: ${audit.summary || ''}`,
        `Agent F1: ${((audit.agent_f1_score || 0) * 100).toFixed(0)}%`,
        `Satisfaction: ${audit.satisfaction_prediction || ''}`,
        `Compliance Risk: ${audit.compliance_risk || ''}`,
        `Flags: ${(audit.compliance_flags || []).join('; ') || 'None'}`,
        `Nudges: ${(audit.behavioral_nudges || []).join('; ')}`,
    ].join('\n');
    navigator.clipboard.writeText(text).then(() => notify('Audit report copied', 'success'));
});

// ── Archive ───────────────────────────────────────────────────────────────
function archiveAudit(data) {
    const audit = data.audit || {};
    AppState.history.unshift({
        id: Date.now(),
        type: data.type,
        audit,
        transcription: data.transcription || null,
        original_text: data.original_text || null,
        timestamp: data.timestamp || new Date().toISOString(),
    });
    if (AppState.history.length > 50) AppState.history = AppState.history.slice(0, 50);
    localStorage.setItem('brieflyqa_history', JSON.stringify(AppState.history));
}

function renderArchive() {
    if (!AppState.history.length) {
        UI.historyList.innerHTML = `<div class="empty-state">
            <span class="material-symbols-rounded" style="font-size:2.5rem;opacity:0.3">history</span>
            <p>No audits yet. Process a call or chat to begin.</p>
        </div>`;
        return;
    }
    UI.historyList.innerHTML = AppState.history.map(item => {
        const audit = item.audit || {};
        const f1 = typeof audit.agent_f1_score === 'number' ? (audit.agent_f1_score * 100).toFixed(0) + '%' : '—';
        const risk = audit.compliance_risk || '—';
        return `<div class="history-card" data-id="${item.id}">
            <div class="history-header">
                <span class="item-type">${item.type === 'chat' ? 'TEXT' : 'VOICE'}</span>
                <span class="item-time">${formatTimeAgo(new Date(item.timestamp))}</span>
                <span class="item-f1">F1: ${f1}</span>
                <span class="item-risk risk-${risk.toLowerCase()}">${risk}</span>
            </div>
            <div class="item-preview">${escHtml(audit.summary || 'No summary.')}</div>
        </div>`;
    }).join('');

    $$('.history-card').forEach(card => {
        card.addEventListener('click', () => {
            if (AppState.isProcessing || AppState.isRecording) return;
            const entry = AppState.history.find(h => h.id === parseInt(card.dataset.id));
            if (entry) renderAuditDashboard(entry);
        });
    });
}

// ── Utilities ─────────────────────────────────────────────────────────────
function escHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function formatTranscript(txt) {
    if (!txt) return '';
    // Make speaker labels bold + proper line breaks
    return escHtml(txt)
        .replace(/(Speaker \d+|Agent|Customer|speaker_\d+):/gi, '<strong>$1:</strong>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');
}

function scoreClass(val, [hi, lo]) {
    if (val === null || val === undefined) return '';
    if (val >= hi) return 'kpi-green';
    if (val >= lo) return 'kpi-amber';
    return 'kpi-red';
}
function satClass(s) {
    return s === 'High' ? 'kpi-green' : s === 'Medium' ? 'kpi-amber' : s === 'Low' ? 'kpi-red' : '';
}
function riskClass(r) {
    return r === 'Green' ? 'kpi-green' : r === 'Amber' ? 'kpi-amber' : r === 'Red' ? 'kpi-red' : '';
}

async function apiFetch(path, options = {}) {
    const res = await fetch(`${API_BASE_URL}${path}`, options);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Audit request failed.');
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
    if (s < 10) return 'Just now';
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
        const st = $('#status-text');
        if (data.api_ready) st.textContent = 'Qualora Engine: Active';
        else st.textContent = 'Qualora Engine: Limited Mode';
    } catch {
        UI.infoBar.classList.add('status-offline');
        $('#status-text').textContent = 'Qualora Engine: Offline';
    }
}

// ── Init ──────────────────────────────────────────────────────────────────
syncInteractiveState();
verifyConnection();
setInterval(verifyConnection, 30000);
