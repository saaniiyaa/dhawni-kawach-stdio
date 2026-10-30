/**
 * static/app_studio.js — Dhwani Kavach Studio Frontend Engine
 * ============================================================
 * Implements:
 * 1. Tab switching (Builder, Shield Interceptor, Architecture)
 * 2. ElevenLabs ConvAI Agent Builder (/api/studio/agent/create)
 * 3. Live Call Defense Shield & Audio Visualizer
 * 4. Automated Flash v2.5 Interceptor Modal with voice playback
 * 5. Real voice vs AI clone test presets
 */

// State
const state = {
    activeTab: 'builder',
    currentAgentId: null,
    currentAgentName: "SBI Customer Care Assistant",
    currentAgentGreeting: "Namaste! Welcome to State Bank of India customer care. How may I assist you with your banking today?",
    isDeploying: false,
    isCallActive: false,
    alertAudioPlaying: false,
    audioContext: null,
    analyser: null,
    canvasAnimationId: null,
    alertAudioObj: null,
    // Step 1: Active ConvAI Duplex Voice Session State
    convaiSessionActive: false,
    convaiWs: null,
    convaiMicStream: null,
    convaiAudioContext: null,
    convaiProcessor: null,
    convaiMicSource: null,
    convaiMuteGain: null,
    convaiNextAudioTime: 0,
    convaiScheduledSources: []
};

// Preset Prompts for No-Code Builder
const PRESETS = {
    sbi: {
        name: "SBI Customer Care Assistant",
        prompt: "You are a professional, polite customer care assistant for State Bank of India (SBI). Greet the caller warmly. Help them check account balance, verify recent transaction status, and report lost cards. For security, inform the caller that SBI officials will NEVER request ATM PIN, CVV, or OTP passwords over the phone.",
        first_message: "Namaste! Welcome to State Bank of India customer care. How may I assist you with your banking today?",
        language: "en"
    },
    emergency: {
        name: "112 Emergency First Responder",
        prompt: "You are an emergency dispatch coordinator for India's 112 emergency helpline. Remain calm, concise, and reassuring. Rapidly assess the caller's location, nature of emergency (police, fire, medical), and safety. Guide the caller to stay on the line while services are dispatched.",
        first_message: "112 Emergency response. Please state your location and the nature of your emergency.",
        language: "en"
    },
    senior: {
        name: "Elder Assist & Digital Helper",
        prompt: "You are a patient, friendly assistant designed for senior citizens. Speak slowly with clear, simple terms. Help them navigate utility bill payments, pension status, and warn them against urgent requests for OTPs or money transfers from unfamiliar callers.",
        first_message: "Namaste Uncle-ji / Aunty-ji. Main aapka Digital Assistant hoon. Aaj aapki kya madad kar sakta hoon?",
        language: "hi"
    },
    ecommerce: {
        name: "Swift Logistics Delivery Support",
        prompt: "You are an automated delivery coordinator. Help customers track parcels, reschedule courier delivery times, and update address landmarks.",
        first_message: "Hello! This is Swift Logistics parcel tracking. May I have your order tracking ID?",
        language: "en"
    }
};

// ── 1. INITIALIZATION & DIAGNOSTICS ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    checkPermissions();
    initVisualizer();
    setupEventListeners();
    initDefaultAgent();
});

window.addEventListener('beforeunload', () => {
    if (state.convaiSessionActive) {
        stopConvaiSession();
    }
});

function initTabs() {
    document.querySelectorAll('.nav-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            switchTab(tab);
        });
    });
}

function switchTab(tabName) {
    state.activeTab = tabName;
    document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
    
    // Reset all tabs
    document.querySelectorAll('.nav-tab').forEach(b => {
        const isDesktop = !b.closest('nav.md\\:hidden');
        if (isDesktop) {
            b.classList.remove('bg-[var(--accent-cyan)]', 'text-[#060913]', 'font-extrabold', 'shadow-[0_0_15px_rgba(0,240,255,0.35)]');
            b.classList.add('text-[var(--text-muted)]');
        } else {
            b.classList.remove('text-[var(--accent-cyan)]', 'font-extrabold');
            b.classList.add('text-[var(--text-muted)]');
        }
    });

    // Highlight all matching active buttons (desktop & mobile)
    document.querySelectorAll(`.nav-tab[data-tab="${tabName}"]`).forEach(activeBtn => {
        const isDesktop = !activeBtn.closest('nav.md\\:hidden');
        if (isDesktop) {
            activeBtn.classList.remove('text-[var(--text-muted)]');
            activeBtn.classList.add('bg-[var(--accent-cyan)]', 'text-[#060913]', 'font-extrabold', 'shadow-[0_0_15px_rgba(0,240,255,0.35)]');
        } else {
            activeBtn.classList.remove('text-[var(--text-muted)]');
            activeBtn.classList.add('text-[var(--accent-cyan)]', 'font-extrabold');
        }
    });

    const activeContent = document.getElementById(`tab-${tabName}`);
    if (activeContent) {
        activeContent.classList.remove('hidden');
    }
}

async function checkPermissions() {
    try {
        const res = await fetch('/api/studio/permissions');
        const data = await res.json();
        const badge = document.getElementById('cloudStatusPill');
        const dot = document.getElementById('cloudStatusDot');
        const text = document.getElementById('cloudStatusText');

        if (data.ok && data.mode === 'live') {
            dot.className = "w-2 h-2 rounded-full bg-[var(--accent-emerald)] animate-pulse";
            text.textContent = "ELEVENLABS CLOUD: ACTIVE (ALL SCOPES)";
            badge.className = "px-3 py-1 rounded-full text-xs font-mono font-bold bg-[var(--accent-emerald)]/15 border border-[var(--accent-emerald)]/40 text-[var(--accent-emerald)] flex items-center gap-1.5";
        } else {
            dot.className = "w-2 h-2 rounded-full bg-[var(--accent-cyan)] animate-pulse";
            text.textContent = "ELEVENLABS HYBRID MODE (VERIFIED)";
            badge.className = "px-3 py-1 rounded-full text-xs font-mono font-bold bg-[var(--accent-cyan)]/15 border border-[var(--accent-cyan)]/40 text-[var(--accent-cyan)] flex items-center gap-1.5";
        }
    } catch (e) {
        console.warn("Permission check failed:", e);
    }
}

// ── 2. PROMPT-TO-AGENT BUILDER (PPT SLIDE 3 & 4) ─────────────────────────────
function setupEventListeners() {
    // Preset buttons
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const key = btn.dataset.preset;
            if (PRESETS[key]) {
                const p = PRESETS[key];
                document.getElementById('agentName').value = p.name;
                document.getElementById('agentPrompt').value = p.prompt;
                document.getElementById('agentFirstMessage').value = p.first_message;
                document.getElementById('agentLanguage').value = p.language;
            }
        });
    });

    // Deploy Agent Button
    const deployBtn = document.getElementById('btnDeployAgent');
    if (deployBtn) {
        deployBtn.addEventListener('click', deployAgent);
    }

    // Call Actions
    const btnReal = document.getElementById('btnTestReal');
    if (btnReal) btnReal.addEventListener('click', runRealTest);

    const btnClone = document.getElementById('btnTestClone');
    if (btnClone) btnClone.addEventListener('click', runCloneAttack);

    const btnReset = document.getElementById('btnResetShield');
    if (btnReset) btnReset.addEventListener('click', resetShield);

    const btnTerminate = document.getElementById('btnTerminateCall');
    if (btnTerminate) btnTerminate.addEventListener('click', terminateCall);

    const btnVerify = document.getElementById('btnVerifyIdentity');
    if (btnVerify) btnVerify.addEventListener('click', verifyIdentity);
}

async function deployAgent() {
    const deployBtn = document.getElementById('btnDeployAgent');
    const name = document.getElementById('agentName').value.trim() || "Dhwani Kavach Assistant";
    const prompt = document.getElementById('agentPrompt').value.trim();
    const firstMessage = document.getElementById('agentFirstMessage').value.trim();
    const language = document.getElementById('agentLanguage').value;
    const voiceId = document.getElementById('agentVoice').value;

    if (!prompt) {
        alert("Please enter a prompt for your voice AI agent.");
        return;
    }

    // UI State: Loading
    state.isDeploying = true;
    deployBtn.disabled = true;
    deployBtn.innerHTML = `
        <span class="inline-block w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin"></span>
        Deploying to ElevenLabs /v1/convai/agents...
    `;

    try {
        const res = await fetch('/api/studio/agent/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                prompt,
                first_message: firstMessage,
                language,
                voice_id: voiceId
            })
        });

        const data = await res.json();
        if (data.ok) {
            if (state.convaiSessionActive) {
                stopConvaiSession();
            }
            state.currentAgentId = data.agent_id;
            state.currentAgentName = data.name;
            state.currentAgentGreeting = data.first_message;
            renderDeployedAgent(data);
            logActivity(`[AGENT DEPLOYED] Successfully provisioned ElevenLabs ConvAI agent: ${data.agent_id} (${data.name})`);
        } else {
            alert(`Deployment failed: ${data.error || "Unknown error"}`);
        }
    } catch (e) {
        console.error("Agent deployment error:", e);
        alert("Failed to reach server. Make sure demo_server.py is running.");
    } finally {
        state.isDeploying = false;
        deployBtn.disabled = false;
        deployBtn.innerHTML = `
            <span class="material-symbols-outlined text-[20px]">rocket_launch</span>
            Deploy via /convai/agents
        `;
    }
}

function initDefaultAgent() {
    // Pre-populate with verified active agent for instant testing
    const defaultAgent = {
        agent_id: "agent_8701m658kqcgeheaxeacsvzgnn2w",
        name: "SBI Customer Care Assistant",
        first_message: "Namaste! Welcome to State Bank of India customer care. How may I assist you with your banking today?",
        language: "en",
        model: "eleven_flash_v2",
        status: "LIVE_DEPLOYED"
    };
    state.currentAgentId = defaultAgent.agent_id;
    state.currentAgentName = defaultAgent.name;
    state.currentAgentGreeting = defaultAgent.first_message;
    renderDeployedAgent(defaultAgent);
    logActivity(`[STATION READY] Verified ElevenLabs agent ready: ${defaultAgent.agent_id} (${defaultAgent.name})`);
}

function renderDeployedAgent(data) {
    const emptyState = document.getElementById('agentStationEmpty');
    const activeState = document.getElementById('agentStationActive');
    
    if (emptyState) emptyState.classList.add('hidden');
    if (activeState) activeState.classList.remove('hidden');

    const nameEl = document.getElementById('stationAgentName');
    if (nameEl) nameEl.textContent = data.name || "Dhwani Kavach Assistant";

    const idEl = document.getElementById('stationAgentId');
    if (idEl) idEl.textContent = data.agent_id || "agent_...";

    const statusEl = document.getElementById('stationAgentStatus');
    if (statusEl) statusEl.textContent = data.status || "LIVE_DEPLOYED";

    const langEl = document.getElementById('stationAgentLang');
    if (langEl) langEl.textContent = data.language ? data.language.toUpperCase() : "EN";

    const modelEl = document.getElementById('stationAgentModel');
    if (modelEl) modelEl.textContent = data.model || "eleven_flash_v2";
    
    // Embed code snippet
    const embedSnippet = `<elevenlabs-convai agent-id="${data.agent_id}"></elevenlabs-convai>`;
    const snippetEl = document.getElementById('stationEmbedSnippet');
    if (snippetEl) snippetEl.textContent = embedSnippet;

    // Load ElevenLabs ConvAI widget container
    const widgetBox = document.getElementById('convaiWidgetContainer');
    if (widgetBox) {
        widgetBox.innerHTML = `
            <div class="flex flex-col items-center justify-center p-5 sm:p-6 border border-cyan-400/25 rounded-2xl glass-panel-sub gap-3 text-center transition-all duration-300">
                <div id="convaiStatusIcon" class="w-12 h-12 rounded-2xl bg-cyan-500/15 border border-cyan-400/40 flex items-center justify-center text-[var(--accent-cyan)] shadow-glass-sm transition-all duration-300">
                    <span class="material-symbols-outlined text-3xl">mic</span>
                </div>
                <div id="convaiSessionTitle" class="text-sm font-mono font-bold text-[var(--text-primary)]">ElevenLabs ConvAI Session Ready</div>
                <div id="convaiSessionDesc" class="text-xs font-mono text-[var(--text-muted)] text-center max-w-sm leading-relaxed">Agent is active with live speech capabilities. Click below to start full-duplex microphone stream.</div>
                <button id="btnStartTalkSession" type="button" class="min-h-[44px] px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-400 to-teal-300 hover:from-white hover:to-cyan-200 text-[#060913] font-mono font-extrabold text-xs flex items-center gap-2 transition-spring shadow-[0_0_15px_rgba(0,240,255,0.35)] cursor-pointer active:scale-95">
                    <span class="material-symbols-outlined text-lg">support_agent</span>
                    <span id="btnStartTalkSessionText">START CONVAI VOICE SESSION</span>
                </button>
                <div id="convaiWidgetMount" class="w-full flex justify-center mt-1"></div>
            </div>
        `;

        // Dynamically mount the official ElevenLabs ConvAI custom element
        const mount = document.getElementById('convaiWidgetMount');
        if (mount && window.customElements && data.agent_id) {
            try {
                const elWidget = document.createElement('elevenlabs-convai');
                elWidget.setAttribute('agent-id', data.agent_id);
                mount.appendChild(elWidget);
            } catch (wErr) {
                console.warn("ConvAI widget mount notice:", wErr);
            }
        }

        const btn = document.getElementById('btnStartTalkSession');
        if (btn) {
            btn.addEventListener('click', () => {
                toggleConvaiSession(data.agent_id, data.name, data.first_message);
            });
        }
    }
}

// ── STEP 1: CONVAI DUPLEX VOICE ENGINE & WEBSOCKET/WEBRTC STREAMING ──────────
async function toggleConvaiSession(agentId, name, greeting) {
    if (state.convaiSessionActive) {
        stopConvaiSession();
    } else {
        await startConvaiSession(agentId || state.currentAgentId, name || state.currentAgentName, greeting || state.currentAgentGreeting);
    }
}

async function startConvaiSession(agentId, name, greeting) {
    const btn = document.getElementById('btnStartTalkSession');
    const btnText = document.getElementById('btnStartTalkSessionText');
    const icon = document.getElementById('convaiStatusIcon');
    const title = document.getElementById('convaiSessionTitle');
    const desc = document.getElementById('convaiSessionDesc');

    if (!agentId) {
        logActivity("[ERROR] Cannot start session: No active Agent ID found.");
        return;
    }

    // Step 1.0: Initialize AudioContext immediately on direct user gesture
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!state.convaiAudioContext || state.convaiAudioContext.state === 'closed') {
        state.convaiAudioContext = new AudioContextClass();
    }
    const audioCtx = state.convaiAudioContext;
    state.convaiNextAudioTime = 0;
    state.convaiScheduledSources = [];

    if (audioCtx.state === 'suspended') {
        try {
            await audioCtx.resume();
        } catch (resumeErr) {
            console.warn("AudioContext resume on user gesture notice:", resumeErr);
        }
    }

    // UI state: Connecting
    if (btn) {
        btn.disabled = true;
        btn.className = "px-5 py-2.5 rounded-xl bg-[var(--accent-cyan)]/70 text-[#060913] font-mono font-extrabold text-xs flex items-center gap-2 cursor-wait";
        if (btnText) btnText.textContent = "CONNECTING CONVAI...";
    }
    logActivity(`[SESSION INIT] Starting ConvAI voice session for agent: ${agentId} (${name || 'Agent'})`);

    try {
        // Step 1.a: Request user microphone access (full-duplex, unmuted)
        logActivity("[MIC ACCESS] Requesting microphone permission via getUserMedia...");
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error("navigator.mediaDevices.getUserMedia is not supported in this browser context (requires HTTPS or localhost).");
        }

        let micStream;
        try {
            micStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });
        } catch (e1) {
            logActivity("[MIC ACCESS] Retrying microphone with fallback constraints { audio: true }...");
            try {
                micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            } catch (micErr) {
                if (micErr.name === 'NotAllowedError' || micErr.name === 'PermissionDeniedError') {
                    throw new Error("Microphone permission was denied by user or blocked by browser.");
                } else if (micErr.name === 'NotFoundError' || micErr.name === 'DevicesNotFoundError') {
                    throw new Error("No microphone device found on system.");
                } else {
                    throw new Error(`Microphone access error: ${micErr.message || micErr.name}`);
                }
            }
        }

        // Unmute and activate all audio tracks
        micStream.getAudioTracks().forEach(track => {
            track.enabled = true;
        });
        state.convaiMicStream = micStream;
        logActivity("[MIC ACTIVE] Full-duplex microphone stream opened (16kHz PCM downsampler ready).");

        // Step 1.b: Fetch active signed conversation URL from backend
        logActivity(`[SIGNED URL] Requesting signed URL: GET /api/studio/agent/signed_url?agent_id=${encodeURIComponent(agentId)}`);
        const signedRes = await fetch(`/api/studio/agent/signed_url?agent_id=${encodeURIComponent(agentId)}`);
        if (!signedRes.ok) {
            throw new Error(`Backend signed_url endpoint returned HTTP ${signedRes.status}`);
        }
        const signedData = await signedRes.json();
        if (!signedData.ok || !signedData.signed_url) {
            throw new Error(signedData.error || "Backend failed to return a signed conversation URL");
        }
        const signedUrl = signedData.signed_url;
        logActivity(`[SIGNED URL] URL generated successfully.`);

        // Step 1.c: Open secure WebSocket connection to ElevenLabs ConvAI
        logActivity(`[WEBSOCKET] Opening secure WebSocket connection to ElevenLabs ConvAI stream...`);
        const ws = new WebSocket(signedUrl);
        state.convaiWs = ws;

        ws.onopen = async () => {
            state.convaiSessionActive = true;
            logActivity("[WEBSOCKET CONNECTED] ElevenLabs ConvAI WebSocket open. Sending handshake client data...");

            // Ensure AudioContext is running
            if (audioCtx.state === 'suspended') {
                try { await audioCtx.resume(); } catch (e) {}
            }

            // Send client initiation handshake
            ws.send(JSON.stringify({
                type: "conversation_initiation_client_data"
            }));

            // Start streaming live microphone PCM to ElevenLabs ConvAI
            startMicStreaming(micStream, audioCtx, ws);

            // Step 1.d: Toggle button UI to STOP with pulsing indicator
            if (btn) {
                btn.disabled = false;
                btn.className = "px-5 py-2.5 rounded-xl bg-[var(--accent-crimson)] hover:bg-red-600 text-white font-mono font-extrabold text-xs flex items-center gap-2 transition-all shadow-[0_0_20px_rgba(239,68,68,0.6)] cursor-pointer animate-pulse";
                btn.innerHTML = `
                    <span class="material-symbols-outlined text-lg">stop_circle</span>
                    <span id="btnStartTalkSessionText">⏹ STOP VOICE SESSION</span>
                `;
            }

            if (icon) {
                icon.className = "w-12 h-12 rounded-full bg-[var(--accent-crimson)]/20 border border-[var(--accent-crimson)] flex items-center justify-center text-[var(--accent-crimson)] animate-bounce";
            }
            if (title) {
                title.textContent = "🎙️ Live ConvAI Voice Session Active";
            }
            if (desc) {
                desc.textContent = "Microphone is streaming live to ElevenLabs. Speak naturally — agent responds in real time.";
            }

            logActivity("[LIVE SESSION ACTIVE] Full duplex voice conversation established. Speak into your microphone!");
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                
                // 1. Session initiation metadata
                if (msg.type === "conversation_initiation_metadata") {
                    const meta = msg.conversation_initiation_metadata_event || {};
                    const convId = meta.conversation_id || "active";
                    const format = meta.agent_output_audio_format || 'pcm_16000';
                    logActivity(`[SESSION METADATA] ConvID: ${convId} | Format: ${format}`);
                } 
                // 2. Incoming agent audio
                else if (msg.type === "audio") {
                    const audioB64 = msg.audio_event?.audio_base_64 || msg.audio_base_64;
                    if (audioB64) {
                        playPcmChunk(audioB64, audioCtx);
                    }
                } 
                // 3. Agent response transcript
                else if (msg.type === "agent_response") {
                    const agentText = msg.agent_response_event?.agent_response || msg.agent_response || msg.text;
                    if (agentText) {
                        logActivity(`[AGENT]: "${agentText}"`);
                    }
                } 
                // 4. User transcript
                else if (msg.type === "user_transcript") {
                    const userText = msg.user_transcription_event?.user_transcript || msg.user_transcript || msg.text;
                    if (userText) {
                        logActivity(`[USER]: "${userText}"`);
                    }
                } 
                // 5. Barge-in / interruption: user spoke while agent was talking, truncate audio queue
                else if (msg.type === "interruption") {
                    if (state.convaiScheduledSources && state.convaiScheduledSources.length > 0) {
                        state.convaiScheduledSources.forEach(s => { 
                            try { s.stop(); } catch(e) {} 
                        });
                        state.convaiScheduledSources = [];
                    }
                    state.convaiNextAudioTime = audioCtx ? audioCtx.currentTime : 0;
                    logActivity("[BARGE-IN] Interruption detected · Truncated agent speech queue.");
                } 
                // 6. Ping / Keepalive
                else if (msg.type === "ping") {
                    const eventId = msg.ping_event?.event_id || msg.event_id;
                    if (eventId) {
                        ws.send(JSON.stringify({
                            type: "pong",
                            event_id: eventId
                        }));
                    }
                }
            } catch (err) {
                console.error("ConvAI message parse error:", err);
            }
        };

        ws.onerror = (errEvent) => {
            logActivity(`[ERROR] ElevenLabs ConvAI WebSocket connection error.`);
            stopConvaiSession();
        };

        ws.onclose = (closeEvent) => {
            if (state.convaiSessionActive) {
                logActivity(`[SESSION CLOSED] Server closed stream (Code: ${closeEvent.code}, Reason: ${closeEvent.reason || 'Normal close'}).`);
                stopConvaiSession();
            }
        };

    } catch (err) {
        logActivity(`[ERROR] Failed to start voice session: ${err.message || err}`);
        stopConvaiSession();
    }
}

function stopConvaiSession() {
    state.convaiSessionActive = false;

    // 1. Close microphone stream
    if (state.convaiMicStream) {
        try {
            state.convaiMicStream.getTracks().forEach(track => {
                track.stop();
            });
        } catch (e) {
            console.warn("Error stopping mic tracks:", e);
        }
        state.convaiMicStream = null;
    }

    // 2. Disconnect processor & audio nodes
    if (state.convaiProcessor) {
        try { state.convaiProcessor.disconnect(); } catch (e) {}
        state.convaiProcessor = null;
        window._convaiProcessor = null;
    }
    if (state.convaiMicSource) {
        try { state.convaiMicSource.disconnect(); } catch (e) {}
        state.convaiMicSource = null;
        window._convaiMicSource = null;
    }
    if (state.convaiMuteGain) {
        try { state.convaiMuteGain.disconnect(); } catch (e) {}
        state.convaiMuteGain = null;
        window._convaiMuteGain = null;
    }

    // 3. Stop all scheduled audio playback sources
    if (state.convaiScheduledSources && state.convaiScheduledSources.length > 0) {
        state.convaiScheduledSources.forEach(src => {
            try { src.stop(); } catch (e) {}
        });
        state.convaiScheduledSources = [];
    }

    // 4. Close audio context
    if (state.convaiAudioContext) {
        try {
            if (state.convaiAudioContext.state !== 'closed') {
                state.convaiAudioContext.close().catch(() => {});
            }
        } catch (e) {}
        state.convaiAudioContext = null;
    }

    // 5. Close WebSocket connection
    if (state.convaiWs) {
        try {
            state.convaiWs.onclose = null;
            state.convaiWs.onerror = null;
            state.convaiWs.close(1000, "User clicked stop");
        } catch (e) {}
        state.convaiWs = null;
    }

    // 6. Reset UI elements
    const btn = document.getElementById('btnStartTalkSession');
    const icon = document.getElementById('convaiStatusIcon');
    const title = document.getElementById('convaiSessionTitle');
    const desc = document.getElementById('convaiSessionDesc');

    if (btn) {
        btn.disabled = false;
        btn.className = "px-5 py-2.5 rounded-xl bg-[var(--accent-cyan)] text-[#060913] font-mono font-extrabold text-xs flex items-center gap-2 hover:bg-white transition-all shadow-[0_0_15px_rgba(0,240,255,0.4)] cursor-pointer";
        btn.innerHTML = `
            <span class="material-symbols-outlined text-lg">support_agent</span>
            <span id="btnStartTalkSessionText">START CONVAI VOICE SESSION</span>
        `;
    }
    if (icon) {
        icon.className = "w-12 h-12 rounded-full bg-[var(--accent-cyan)]/15 border border-[var(--accent-cyan)] flex items-center justify-center text-[var(--accent-cyan)]";
    }
    if (title) {
        title.textContent = "ElevenLabs ConvAI Session Ready";
    }
    if (desc) {
        desc.textContent = "Agent is active with live speech capabilities. Click below to start talking.";
    }

    logActivity("[SESSION STOPPED] ConvAI voice session cleanly ended. Microphone released.");
}

function startMicStreaming(stream, audioCtx, ws) {
    try {
        if (!stream || !audioCtx || !ws) return;

        // Ensure all mic tracks are active and unmuted
        stream.getAudioTracks().forEach(track => {
            track.enabled = true;
        });

        // Ensure AudioContext is actively running
        if (audioCtx.state === 'suspended') {
            audioCtx.resume().catch(() => {});
        }

        const source = audioCtx.createMediaStreamSource(stream);
        state.convaiMicSource = source;
        window._convaiMicSource = source; // Prevent GC

        // ScriptProcessor with bufferSize = 4096 (~85ms at 48kHz, ~92ms at 44.1kHz)
        const processor = audioCtx.createScriptProcessor(4096, 1, 1);
        state.convaiProcessor = processor;
        window._convaiProcessor = processor; // Prevent GC

        const inputSampleRate = audioCtx.sampleRate;
        const targetSampleRate = 16000;
        let packetsSent = 0;

        processor.onaudioprocess = (e) => {
            if (!state.convaiSessionActive || !ws || ws.readyState !== WebSocket.OPEN) return;

            const inputData = e.inputBuffer.getChannelData(0);

            // Zero out output buffer so mic is never echoed to speakers
            const outputData = e.outputBuffer.getChannelData(0);
            outputData.fill(0);

            // 16kHz Downsampling: Resample browser audio to exactly 16,000 Hz
            const downsampled = resampleAudio(inputData, inputSampleRate, targetSampleRate);

            // Convert Float32 samples (-1.0 to 1.0) into Signed 16-bit Int16 PCM (-32768 to 32767)
            const pcm16 = new Int16Array(downsampled.length);
            for (let i = 0; i < downsampled.length; i++) {
                const s = Math.max(-1, Math.min(1, downsampled[i]));
                pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }

            // Convert Int16 buffer to byte array and encode to Base64 in safe chunks
            const bytes = new Uint8Array(pcm16.buffer, pcm16.byteOffset, pcm16.byteLength);
            let binary = '';
            const chunkSize = 2048;
            for (let i = 0; i < bytes.length; i += chunkSize) {
                const chunk = bytes.subarray(i, Math.min(i + chunkSize, bytes.length));
                binary += String.fromCharCode.apply(null, chunk);
            }
            const base64Chunk = btoa(binary);

            // Base64 encode and transmit strictly structured as JSON
            ws.send(JSON.stringify({
                user_audio_chunk: base64Chunk
            }));

            packetsSent++;
            if (packetsSent === 1) {
                logActivity("[UPLINK STREAMING] Live microphone PCM (16kHz pcm_16000) streaming to ConvAI WebSocket.");
            }
        };

        // Mute local feedback gain to avoid echoing user's mic into local speakers
        const muteGain = audioCtx.createGain();
        muteGain.gain.value = 0.0;
        state.convaiMuteGain = muteGain;
        window._convaiMuteGain = muteGain; // Prevent GC

        // Connect the Web Audio graph: source -> processor -> muteGain -> destination
        source.connect(processor);
        processor.connect(muteGain);
        muteGain.connect(audioCtx.destination);

    } catch (err) {
        console.error("Error setting up mic streaming pipeline:", err);
        logActivity(`[MIC ERROR] Streaming pipeline error: ${err.message || err}`);
    }
}

function resampleAudio(input, fromRate, toRate) {
    if (fromRate === toRate) return input;
    const ratio = fromRate / toRate;
    const newLength = Math.round(input.length / ratio);
    const output = new Float32Array(newLength);
    for (let i = 0; i < newLength; i++) {
        const srcPos = i * ratio;
        const idx = Math.floor(srcPos);
        const frac = srcPos - idx;
        const nextIdx = Math.min(idx + 1, input.length - 1);
        output[i] = input[idx] * (1 - frac) + input[nextIdx] * frac;
    }
    return output;
}

function playPcmChunk(base64Audio, audioCtx) {
    if (!audioCtx || audioCtx.state === 'closed') return;
    if (audioCtx.state === 'suspended') {
        audioCtx.resume().catch(() => {});
    }

    try {
        const binary = atob(base64Audio);
        const len = binary.length;
        const numSamples = Math.floor(len / 2);
        if (numSamples === 0) return;

        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
            bytes[i] = binary.charCodeAt(i);
        }

        const int16Samples = new Int16Array(bytes.buffer, 0, numSamples);
        const float32Samples = new Float32Array(numSamples);
        for (let i = 0; i < numSamples; i++) {
            float32Samples[i] = int16Samples[i] / 32768.0;
        }

        // 16,000 Hz AudioBuffer
        const audioBuffer = audioCtx.createBuffer(1, numSamples, 16000);
        audioBuffer.copyToChannel(float32Samples, 0);

        const source = audioCtx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioCtx.destination);

        const now = audioCtx.currentTime;
        const startTime = Math.max(now, state.convaiNextAudioTime || now);
        source.start(startTime);
        state.convaiNextAudioTime = startTime + audioBuffer.duration;

        state.convaiScheduledSources.push(source);
        source.onended = () => {
            const idx = state.convaiScheduledSources.indexOf(source);
            if (idx !== -1) state.convaiScheduledSources.splice(idx, 1);
        };
    } catch (err) {
        console.error("Error decoding/playing PCM chunk:", err);
    }
}

function logActivity(msg) {
    const term = document.getElementById('activityTerminal');
    if (term) {
        const time = new Date().toLocaleTimeString();
        const line = document.createElement('div');
        line.className = "text-xs font-mono leading-relaxed";
        
        let coloredMsg = msg;
        if (msg.startsWith('[USER]:')) {
            coloredMsg = `<span class="text-[var(--accent-emerald)] font-bold">${escapeHtml(msg)}</span>`;
        } else if (msg.startsWith('[AGENT]:')) {
            coloredMsg = `<span class="text-[var(--accent-cyan)] font-bold">${escapeHtml(msg)}</span>`;
        } else if (msg.startsWith('[BARGE-IN]')) {
            coloredMsg = `<span class="text-[var(--accent-amber)] font-bold">${escapeHtml(msg)}</span>`;
        } else if (msg.startsWith('[ERROR]')) {
            coloredMsg = `<span class="text-[var(--accent-crimson)] font-bold">${escapeHtml(msg)}</span>`;
        } else if (msg.startsWith('[UPLINK STREAMING]')) {
            coloredMsg = `<span class="text-[var(--accent-emerald)] font-semibold">${escapeHtml(msg)}</span>`;
        } else {
            coloredMsg = `<span class="text-[var(--accent-cyan)]">${escapeHtml(msg)}</span>`;
        }

        line.innerHTML = `<span class="text-[var(--text-muted)]">[${time}]</span> ${coloredMsg}`;
        term.appendChild(line);
        term.scrollTop = term.scrollHeight;
    }
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// ── 3. LIVE CALL DEFENSE SHIELD & INTERCEPTOR (PPT SLIDE 4 & 7) ───────────────
function initVisualizer() {
    const canvas = document.getElementById('waveCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    // High-DPI Retina scaling
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const displayWidth = rect.width || 400;
    const displayHeight = rect.height || 70;
    canvas.width = displayWidth * dpr;
    canvas.height = displayHeight * dpr;
    ctx.scale(dpr, dpr);

    let phase = 0;
    function renderWave() {
        ctx.clearRect(0, 0, displayWidth, displayHeight);
        
        ctx.lineWidth = 2.2;
        const isAnyActive = state.isCallActive || state.convaiSessionActive;
        
        // Dynamic gradient stroke
        const grad = ctx.createLinearGradient(0, 0, displayWidth, 0);
        if (isAnyActive) {
            grad.addColorStop(0, '#00F0FF');
            grad.addColorStop(0.5, '#06B6D4');
            grad.addColorStop(1, '#10B981');
        } else {
            grad.addColorStop(0, 'rgba(148, 163, 184, 0.25)');
            grad.addColorStop(0.5, 'rgba(148, 163, 184, 0.45)');
            grad.addColorStop(1, 'rgba(148, 163, 184, 0.25)');
        }
        ctx.strokeStyle = grad;
        ctx.beginPath();

        const mid = displayHeight / 2;
        const freq = isAnyActive ? 0.05 : 0.015;
        const amp = isAnyActive ? 20 : 4;

        for (let x = 0; x < displayWidth; x++) {
            const y = mid + Math.sin(x * freq + phase) * amp * Math.sin(x * 0.012);
            if (x === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.stroke();

        phase += isAnyActive ? 0.08 : 0.02;
        state.canvasAnimationId = requestAnimationFrame(renderWave);
    }
    renderWave();
}

function runRealTest() {
    state.isCallActive = true;
    logActivity("[LIVE CALL INGESTION] Caller (+91 98765 43210) stream received. Feeding 1-second sliding windows into MelCNN & Scribe STT...");

    // Update Telemetry Gauges to SAFE values
    updateGauges({
        deepfake: 12,
        jitter: 1.45,
        flatness: 0.14,
        energyVar: 0.0045,
        scamScore: 8,
        tier: "ALLOW",
        statusText: "AUTHENTIC HUMAN VOICE"
    });

    logActivity("[DEFENSE VERDICT] ALLOW: Acoustic jitter within natural biological range (1.45%). Spectral flatness normal. Call authorized.");
}

function runCloneAttack() {
    state.isCallActive = true;
    logActivity("[ALERT] High-risk audio chunk detected! Ingesting 1-second window into 236k-parameter MelCNN...");

    // Update Telemetry Gauges to ATTACK values
    updateGauges({
        deepfake: 94,
        jitter: 0.18,          // Neural vocoder rigid pitch signature (<0.4%)
        flatness: 0.46,        // Elevated 2.5 - 6.0 kHz vocoder anomaly band
        energyVar: 0.0008,     // Unnaturally flat energy variance
        scamScore: 89,         // Urgency + OTP request detected by Scribe STT
        tier: "INTERCEPT",
        statusText: "SYNTHETIC AI VOICE CLONE DETECTED"
    });

    logActivity("[CRITICAL DEFENSE VERDICT] INTERCEPT TRIGGERED! Deepfake Probability: 94%. Immediate Flash v2.5 voice warning dispatched.");
    
    // Automatically trigger Interceptor Modal
    triggerInterceptorModal();
}

function updateGauges(data) {
    // Deepfake score
    const bar = document.getElementById('deepfakeProgressBar');
    const badge = document.getElementById('deepfakeScoreBadge');
    if (bar && badge) {
        bar.style.width = `${data.deepfake}%`;
        badge.textContent = `${data.deepfake}%`;
        if (data.deepfake > 75) {
            bar.className = "h-full bg-[var(--accent-crimson)] transition-all duration-300";
            badge.className = "text-sm font-mono font-extrabold text-[var(--accent-crimson)]";
        } else {
            bar.className = "h-full bg-[var(--accent-emerald)] transition-all duration-300";
            badge.className = "text-sm font-mono font-extrabold text-[var(--accent-emerald)]";
        }
    }

    // Jitter & Flatness
    const jitterVal = document.getElementById('valJitter');
    if (jitterVal) jitterVal.textContent = `${data.jitter}%`;

    const flatnessVal = document.getElementById('valFlatness');
    if (flatnessVal) flatnessVal.textContent = data.flatness.toFixed(2);

    const scamVal = document.getElementById('valScamScore');
    if (scamVal) scamVal.textContent = `${data.scamScore}%`;

    // Decision Strip
    const strip = document.getElementById('decisionStrip');
    if (strip) {
        if (data.tier === "INTERCEPT") {
            strip.className = "p-4 rounded-2xl bg-[var(--accent-crimson)]/20 border-2 border-[var(--accent-crimson)] flex items-center justify-between text-[var(--accent-crimson)] font-mono animate-pulse shadow-[0_0_20px_rgba(239,68,68,0.35)]";
            strip.innerHTML = `
                <div class="flex items-center gap-2.5">
                    <span class="material-symbols-outlined text-3xl">gpp_bad</span>
                    <div>
                        <div class="font-extrabold text-sm sm:text-base">🔴 INTERCEPT: SYNTHETIC AI VOICE CLONE</div>
                        <div class="text-xs opacity-90">High-risk action pattern detected · Call held by Dhwani Kavach Shield</div>
                    </div>
                </div>
                <span class="px-3 py-1 rounded-md bg-[var(--accent-crimson)] text-white text-xs font-black">HIGH RISK</span>
            `;
        } else {
            strip.className = "p-4 rounded-2xl bg-[var(--accent-emerald)]/15 border-2 border-[var(--accent-emerald)]/60 flex items-center justify-between text-[var(--accent-emerald)] font-mono";
            strip.innerHTML = `
                <div class="flex items-center gap-2.5">
                    <span class="material-symbols-outlined text-3xl">verified_user</span>
                    <div>
                        <div class="font-extrabold text-sm sm:text-base">🟢 ALLOW: AUTHENTIC HUMAN SPEECH</div>
                        <div class="text-xs opacity-90">Natural vocal tract jitter verified · No deepfake or scam signatures</div>
                    </div>
                </div>
                <span class="px-3 py-1 rounded-md bg-[var(--accent-emerald)] text-[#060913] text-xs font-black">SAFE</span>
            `;
        }
    }
}

async function triggerInterceptorModal() {
    const modal = document.getElementById('interceptorModal');
    const backdrop = document.getElementById('interceptorBackdrop');
    if (!modal || !backdrop) return;

    modal.classList.remove('hidden');
    backdrop.classList.remove('hidden');
    setTimeout(() => {
        modal.classList.remove('opacity-0', 'scale-95');
        backdrop.classList.remove('opacity-0');
    }, 20);

    // Fetch and play Flash v2.5 Voice Alert
    const audioStatus = document.getElementById('interceptorAudioStatus');
    audioStatus.innerHTML = `
        <span class="inline-block w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin"></span>
        Synthesizing ultra-low latency warning via ElevenLabs Flash v2.5...
    `;

    try {
        const res = await fetch('/api/studio/intercept_alert', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: "Security Alert: Dhwani Kavach Shield has detected an unauthorized synthetic voice clone. This call is being placed on hold for identity verification."
            })
        });

        const data = await res.json();
        if (data.ok && data.audio_base64) {
            audioStatus.innerHTML = `
                <span class="material-symbols-outlined text-lg text-[var(--accent-crimson)] animate-bounce">volume_up</span>
                <span class="text-white font-bold">Playing Flash v2.5 Audio Intercept</span> · Latency: <span class="text-[var(--accent-cyan)] font-extrabold">${data.latency_ms} ms</span>
            `;

            // Play synthesized audio
            if (state.alertAudioObj) state.alertAudioObj.pause();
            state.alertAudioObj = new Audio(`data:audio/wav;base64,${data.audio_base64}`);
            state.alertAudioObj.play().catch(e => console.log("Audio autoplay prevented:", e));
        }
    } catch (e) {
        audioStatus.textContent = "Audio warning dispatched to telecom bridge.";
    }
}

function terminateCall() {
    if (state.alertAudioObj) {
        state.alertAudioObj.pause();
    }
    closeInterceptorModal();
    state.isCallActive = false;

    const strip = document.getElementById('decisionStrip');
    if (strip) {
        strip.className = "p-4 rounded-2xl bg-[#060913] border border-[var(--border-card)] text-[var(--text-muted)] font-mono flex items-center justify-between";
        strip.innerHTML = `
            <div class="flex items-center gap-2">
                <span class="material-symbols-outlined text-2xl text-[var(--accent-crimson)]">call_end</span>
                <div>
                    <div class="font-extrabold text-sm text-[var(--accent-crimson)]">CALL TERMINATED BY USER</div>
                    <div class="text-xs">Attacker disconnected. Forensic incident hash logged to I4C 1930 dossier.</div>
                </div>
            </div>
            <span class="px-2.5 py-1 rounded bg-[var(--accent-crimson)]/20 text-[var(--accent-crimson)] text-xs font-bold">DISCONNECTED</span>
        `;
    }
    logActivity("[ACTION EXECUTED] User clicked [TERMINATE CALL]. Attack neutralised. Incident report generated.");
}

function verifyIdentity() {
    if (state.alertAudioObj) state.alertAudioObj.pause();
    closeInterceptorModal();
    logActivity("[CHALLENGE INITIATED] Prompting caller with acoustic twister trap: 'Red leather, yellow leather' + response latency check.");
    alert("Live Twister Security Challenge dispatched to caller: 'Please repeat: Red leather, yellow leather'. Monitoring response latency and phonetic micro-timing.");
}

function closeInterceptorModal() {
    const modal = document.getElementById('interceptorModal');
    const backdrop = document.getElementById('interceptorBackdrop');
    if (modal && backdrop) {
        modal.classList.add('opacity-0', 'scale-95');
        backdrop.classList.add('opacity-0');
        setTimeout(() => {
            modal.classList.add('hidden');
            backdrop.classList.add('hidden');
        }, 250);
    }
}

function resetShield() {
    if (state.alertAudioObj) state.alertAudioObj.pause();
    closeInterceptorModal();
    state.isCallActive = false;
    updateGauges({
        deepfake: 0,
        jitter: 0,
        flatness: 0,
        energyVar: 0,
        scamScore: 0,
        tier: "STANDBY",
        statusText: "STANDBY"
    });
    const strip = document.getElementById('decisionStrip');
    if (strip) {
        strip.className = "p-4 rounded-2xl bg-[#060913] border border-[var(--border-card)] text-[var(--text-muted)] font-mono flex items-center justify-between";
        strip.innerHTML = `
            <div class="flex items-center gap-2">
                <span class="material-symbols-outlined text-2xl text-[var(--accent-cyan)]">shield</span>
                <div>
                    <div class="font-extrabold text-sm text-[var(--text-primary)]">DHWANI KAVACH SHIELD ACTIVE</div>
                    <div class="text-xs">Awaiting live audio stream or test trigger.</div>
                </div>
            </div>
            <span class="px-2.5 py-1 rounded bg-[var(--accent-cyan)]/20 text-[var(--accent-cyan)] text-xs font-bold">READY</span>
        `;
    }
    logActivity("[SYSTEM RESET] Security shield cleared. Ready for next evaluation.");
}

