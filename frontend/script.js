function getApiBase() {
    const { protocol, hostname, port } = window.location;

    if (protocol === "file:") {
        return "http://127.0.0.1:8000";
    }

    if (port === "8000") {
        return "";
    }

    return `${protocol}//${hostname}:8000`;
}

const API = getApiBase();

const state = {
    email: "",
    // In-memory only for testing: refresh returns to Login/Create Account.
    sessionToken: "",
    account: null,
    selectedDocumentId: null,
    documents: [],
    isRecording: false,
    speechRecognition: null,
    speechFinalText: "",
    uploadStageTimer: null,
    currentAudio: null,
    audioContext: null,
    audioPrimed: false,
    currentStrategy: null,
};

const gate = document.getElementById("gate");
const app = document.getElementById("app");
const emailInput = document.getElementById("email-input");
const emailSubmit = document.getElementById("email-submit");
const gateError = document.getElementById("gate-error");
const gateLabel = document.getElementById("gate-label");
const otpStep = document.getElementById("otp-step");
const otpInput = document.getElementById("otp-input");
const otpResend = document.getElementById("otp-resend");
const registerFields = document.getElementById("register-fields");
const companyInput = document.getElementById("company-input");
const promptInput = document.getElementById("prompt-input");
const widgetTitleInput = document.getElementById("widget-title-input");
const widgetWelcomeInput = document.getElementById("widget-welcome-input");
const widgetColorInput = document.getElementById("widget-color-input");
const widgetPositionInput = document.getElementById("widget-position-input");
const tabLogin = document.getElementById("tab-login");
const tabRegister = document.getElementById("tab-register");
const authChoose = document.getElementById("auth-choose");
const authFlow = document.getElementById("auth-flow");
const authBack = document.getElementById("auth-back");
const gateHint = document.getElementById("gate-hint");
const docList = document.getElementById("doc-list");
const docEmpty = document.getElementById("doc-empty");
const docTitle = document.getElementById("doc-title");
const messages = document.getElementById("messages");
const emptyState = document.getElementById("empty-state");
const chatInput = document.getElementById("chat-input");
const sendButton = document.getElementById("send-button");
const micButton = document.getElementById("mic-button");
const fileUpload = document.getElementById("file-upload");
const uploadZone = document.getElementById("upload-zone");
const newChatBtn = document.getElementById("new-chat");
const userEmailEl = document.getElementById("user-email");
const composerNote = document.getElementById("composer-note");
const toast = document.getElementById("toast");
const uploadOverlay = document.getElementById("upload-overlay");
const uploadStatus = document.getElementById("upload-status");
const uploadFilename = document.getElementById("upload-filename");
const uploadSubstatus = document.getElementById("upload-substatus");

function showToast(message) {
    toast.textContent = message;
    toast.hidden = false;
    setTimeout(() => { toast.hidden = true; }, 3200);
}

function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

async function apiFetch(path, options = {}) {
    let response;
    const headers = {
        ...(options.headers || {}),
    };

    if (state.sessionToken) {
        headers["X-Session-Token"] = state.sessionToken;
    }

    try {
        response = await fetch(`${API}${path}`, {
            ...options,
            headers,
        });
    } catch (_) {
        throw new Error(
            "Cannot reach the server. Run the app with: python run.py — then open http://localhost:8000"
        );
    }

    if (!response.ok) {
        let detail = "Something went wrong.";
        try {
            const body = await response.json();
            detail = body.detail || detail;
        } catch (_) {}

        if (response.status === 401) {
            clearSession();
        }

        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }

    if (response.status === 204) {
        return null;
    }

    return response.json();
}

function setComposerEnabled(enabled) {
    chatInput.disabled = !enabled;
    sendButton.disabled = !enabled;
    micButton.disabled = !enabled;
}

function autoResizeTextarea() {
    chatInput.style.height = "auto";
    chatInput.style.height = `${Math.min(chatInput.scrollHeight, 120)}px`;
}

function clearMessages() {
    messages.innerHTML = "";
    messages.appendChild(emptyState);
    emptyState.hidden = false;
}

function setCurrentStrategy(strategy, reason) {
    if (strategy) {
        state.currentStrategy = {
            strategy,
            reason: reason || "",
        };
    } else {
        state.currentStrategy = null;
    }
}

function ensureStrategyCard() {
    if (!state.currentStrategy) return;
    if (document.getElementById("strategy-card")) return;
    showStrategyCard(state.currentStrategy);
}

function renderMessages(history, strategy, reason) {
    setCurrentStrategy(strategy, reason);

    messages.innerHTML = "";
    messages.appendChild(emptyState);

    const hasStrategy = Boolean(state.currentStrategy);
    const hasHistory = history && history.length > 0;

    if (!hasStrategy && !hasHistory) {
        emptyState.hidden = false;
        return;
    }

    emptyState.hidden = true;

    if (hasStrategy) {
        showStrategyCard(state.currentStrategy);
    }

    if (hasHistory) {
        history.forEach((turn) => {
            appendMessage("user", turn.user, false);
            appendMessage("assistant", turn.assistant, false);
        });
    }

    scrollToBottom();
}

function appendMessage(role, text, scroll = true) {
    emptyState.hidden = true;
    ensureStrategyCard();

    const el = document.createElement("div");
    el.className = `message ${role}`;
    el.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
    messages.appendChild(el);

    if (scroll) scrollToBottom();
    return el;
}

function appendTyping() {
    emptyState.hidden = true;
    ensureStrategyCard();
    const el = document.createElement("div");
    el.className = "message assistant typing";
    el.innerHTML = `<div class="bubble">Thinking...</div>`;
    messages.appendChild(el);
    scrollToBottom();
    return el;
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML.replace(/\n/g, "<br>");
}

function scrollToBottom() {
    messages.scrollTop = messages.scrollHeight;
}

function stopSpeech() {
    if (state.currentAudio) {
        state.currentAudio.pause();
        state.currentAudio = null;
    }

    document.querySelectorAll(".message.speaking").forEach((el) => {
        el.classList.remove("speaking");
    });

    if (!state.isRecording) {
        composerNote.textContent = "";
    }
}

function unlockAudio() {
    if (!state.audioContext) {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) {
            state.audioContext = new AudioCtx();
        }
    }

    if (state.audioContext && state.audioContext.state === "suspended") {
        state.audioContext.resume();
    }

    if (!state.audioPrimed) {
        const probe = new Audio();
        probe.muted = true;
        probe.src =
            "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAAAA==";
        probe.play()
            .then(() => {
                probe.pause();
                state.audioPrimed = true;
            })
            .catch(() => {});
    }
}

function base64ToBlob(base64, mimeType) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);

    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }

    return new Blob([bytes], { type: mimeType });
}

async function playAudioBlob(blob, mimeType = "audio/wav", messageEl = null) {
    stopSpeech();
    unlockAudio();

    if (!blob || blob.size === 0) {
        throw new Error("No audio received from the server.");
    }

    const typedBlob = blob.type ? blob : new Blob([blob], { type: mimeType });
    const url = URL.createObjectURL(typedBlob);
    const audio = new Audio(url);

    state.currentAudio = audio;

    if (messageEl) {
        messageEl.classList.add("speaking");
    }

    composerNote.textContent = "Speaking…";

    audio.onended = () => {
        URL.revokeObjectURL(url);

        if (state.currentAudio === audio) {
            state.currentAudio = null;
        }

        if (messageEl) {
            messageEl.classList.remove("speaking");
        }

        if (!state.isRecording) {
            composerNote.textContent = "";
        }
    };

    audio.onerror = () => {
        URL.revokeObjectURL(url);

        if (messageEl) {
            messageEl.classList.remove("speaking");
        }

        if (!state.isRecording) {
            composerNote.textContent = "";
        }

        throw new Error("Audio playback failed.");
    };

    try {
        await audio.play();
    } catch (_) {
        URL.revokeObjectURL(url);

        if (messageEl) {
            messageEl.classList.remove("speaking");
        }

        if (!state.isRecording) {
            composerNote.textContent = "";
        }

        throw new Error(
            "Could not play audio. Click anywhere on the page, then send your message again."
        );
    }
}

async function playAudioBase64(base64, mimeType = "audio/wav", messageEl = null) {
    const blob = base64ToBlob(base64, mimeType);
    await playAudioBlob(blob, mimeType, messageEl);
}

async function speakText(text) {
    let response;

    try {
        response = await fetch(`${API}/api/speak`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text }),
        });
    } catch (_) {
        throw new Error("Cannot reach the voice server.");
    }

    if (!response.ok) {
        let detail = "Voice generation failed.";
        try {
            const body = await response.json();
            detail = body.detail || detail;
        } catch (_) {}
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }

    const blob = await response.blob();
    await playAudioBlob(blob, response.headers.get("content-type") || "audio/wav");
}

function showUploadLoading(filename) {
    uploadFilename.textContent = filename;
    uploadStatus.textContent = "Uploading document";
    uploadSubstatus.textContent = "Sending file to server…";
    uploadOverlay.classList.remove("hidden");
    uploadZone.classList.add("disabled");

    const stages = [
        ["Uploading document", "Sending file to server…"],
        ["Analyzing document", "Reading content and structure…"],
        ["Selecting strategy", "Finding the best chunking approach…"],
        ["Building knowledge base", "Creating searchable embeddings…"],
    ];

    let stageIndex = 0;

    if (state.uploadStageTimer) {
        clearInterval(state.uploadStageTimer);
    }

    state.uploadStageTimer = setInterval(() => {
        stageIndex = Math.min(stageIndex + 1, stages.length - 1);
        uploadStatus.textContent = stages[stageIndex][0];
        uploadSubstatus.textContent = stages[stageIndex][1];
    }, 10000);
}

function hideUploadLoading() {
    uploadOverlay.classList.add("hidden");
    uploadZone.classList.remove("disabled");

    if (state.uploadStageTimer) {
        clearInterval(state.uploadStageTimer);
        state.uploadStageTimer = null;
    }
}

function showStrategyCard(data) {
    setCurrentStrategy(data.strategy, data.reason);

    const existing = document.getElementById("strategy-card");
    if (existing) existing.remove();

    emptyState.hidden = true;

    const card = document.createElement("div");
    card.className = "strategy-card";
    card.id = "strategy-card";
    card.innerHTML = `
        <p class="strategy-label">Recommended chunking strategy</p>
        <p class="strategy-name">${escapeHtml(data.strategy)}</p>
    `;

    if (messages.contains(emptyState)) {
        emptyState.insertAdjacentElement("afterend", card);
    } else {
        messages.prepend(card);
    }

    scrollToBottom();
}

function renderDocuments() {
    docList.innerHTML = "";
    docEmpty.hidden = state.documents.length > 0;

    state.documents.forEach((doc) => {
        const row = document.createElement("div");
        row.className = "doc-row";

        if (doc.document_id === state.selectedDocumentId) {
            row.classList.add("active");
        }

        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "doc-item";
        btn.textContent = doc.filename;
        btn.title = doc.filename;
        btn.addEventListener("click", () => selectDocument(doc.document_id, doc.filename));

        const delBtn = document.createElement("button");
        delBtn.type = "button";
        delBtn.className = "doc-delete";
        delBtn.title = "Delete document";
        delBtn.setAttribute("aria-label", `Delete ${doc.filename}`);
        delBtn.textContent = "×";
        delBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            deleteDocument(doc);
        });

        row.appendChild(btn);
        row.appendChild(delBtn);
        docList.appendChild(row);
    });
}

async function deleteDocument(doc) {
    const ok = window.confirm(`Delete "${doc.filename}"? This cannot be undone.`);
    if (!ok) return;

    try {
        await apiFetch("/api/documents", {
            method: "DELETE",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                email: state.email,
                document_id: doc.document_id,
            }),
        });

        const wasSelected = state.selectedDocumentId === doc.document_id;

        if (wasSelected) {
            stopSpeech();
            state.selectedDocumentId = null;
            state.currentStrategy = null;
            localStorage.removeItem("ka_selected_doc");
            docTitle.textContent = "Document Assistant";
            clearMessages();
            setComposerEnabled(false);
        }

        await loadDocuments({ reselect: false });
        showToast(`Deleted "${doc.filename}"`);
    } catch (err) {
        showToast(err.message);
    }
}

async function loadDocuments({ reselect = true } = {}) {
    const data = await apiFetch("/api/documents", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: state.email }),
    });

    state.documents = data.documents;
    renderDocuments();

    if (reselect && state.selectedDocumentId) {
        const doc = state.documents.find(
            (item) => item.document_id === state.selectedDocumentId
        );

        if (doc) {
            await selectDocument(doc.document_id, doc.filename, true);
            return;
        }

        state.selectedDocumentId = null;
        state.currentStrategy = null;
        localStorage.removeItem("ka_selected_doc");
    }
}

async function selectDocument(documentId, filename, force = false) {
    if (!force && state.selectedDocumentId === documentId) return;

    state.selectedDocumentId = documentId;
    localStorage.setItem("ka_selected_doc", documentId);
    docTitle.textContent = filename || "Document";
    renderDocuments();
    setComposerEnabled(true);
    composerNote.textContent = "";

    const data = await apiFetch(
        `/api/history?email=${encodeURIComponent(state.email)}&document_id=${encodeURIComponent(documentId)}`
    );

    renderMessages(data.history, data.strategy, data.reason);
}

function startSession(email, account = null, sessionToken = null) {
    state.email = email;

    if (sessionToken) {
        state.sessionToken = sessionToken;
    }

    if (account) {
        state.account = account;
        applyAccountBranding(account);
    }

    gate.classList.add("hidden");
    app.classList.remove("hidden");
    userEmailEl.textContent = account?.company_name
        ? `${account.company_name} · ${email}`
        : email;

    const tenantIdEl = document.getElementById("tenant-id");
    if (tenantIdEl) {
        const tenantId = account?.tenant_id || "";
        if (tenantId) {
            tenantIdEl.hidden = false;
            tenantIdEl.textContent = `Tenant ID: ${tenantId}`;
            tenantIdEl.title = "Use this value for data-tenant in the CDN embed script";
        } else {
            tenantIdEl.hidden = true;
            tenantIdEl.textContent = "";
        }
    }

    apiFetch("/api/health").then((data) => {
        if (!data.voice) {
            showToast("CARTESIA_API_KEY is missing — voice responses will not work.");
        }
    }).catch(() => {
        showToast("Server offline — run: python run.py");
    });

    loadDocuments();
}

async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text || !state.selectedDocumentId) return;

    unlockAudio();

    chatInput.value = "";
    autoResizeTextarea();
    appendMessage("user", text);

    const typing = appendTyping();
    sendButton.disabled = true;
    composerNote.textContent = "Thinking and preparing voice…";

    try {
        const data = await apiFetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                email: state.email,
                document_id: state.selectedDocumentId,
                question: text,
            }),
        });

        typing.remove();
        const messageEl = appendMessage("assistant", data.answer);

        if (data.audio) {
            await playAudioBase64(data.audio, data.audio_type, messageEl);
        } else {
            await speakText(data.answer);
        }
    } catch (err) {
        typing.remove();
        appendMessage("assistant", `Error: ${err.message}`);
        showToast(err.message);
        composerNote.textContent = "";
    } finally {
        sendButton.disabled = false;
        chatInput.focus();
    }
}

async function uploadFile(file) {
    if (!file) return;

    showUploadLoading(file.name);

    const formData = new FormData();
    formData.append("email", state.email);
    formData.append("file", file);

    try {
        const data = await apiFetch("/api/upload", {
            method: "POST",
            body: formData,
        });

        hideUploadLoading();

        state.selectedDocumentId = data.document_id;
        localStorage.setItem("ka_selected_doc", data.document_id);
        setCurrentStrategy(data.strategy, data.reason);

        await loadDocuments({ reselect: false });

        docTitle.textContent = data.filename;
        renderDocuments();
        setComposerEnabled(true);

        messages.innerHTML = "";
        messages.appendChild(emptyState);
        emptyState.hidden = true;

        showStrategyCard(state.currentStrategy);
        const welcome = `"${data.filename}" is ready. Ask me anything about it.`;
        appendMessage("assistant", welcome);

        showToast("Document ready");
    } catch (err) {
        hideUploadLoading();
        showToast(err.message);
        composerNote.textContent = "";
    } finally {
        composerNote.textContent = "";
        fileUpload.value = "";
    }
}

function resetConversation() {
    stopSpeech();
    state.selectedDocumentId = null;
    state.currentStrategy = null;
    localStorage.removeItem("ka_selected_doc");
    docTitle.textContent = "Document Assistant";
    clearMessages();
    setComposerEnabled(false);
    renderDocuments();
}

function getSpeechRecognition() {
    return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function stopRecording() {
    state.isRecording = false;

    if (state.speechRecognition) {
        const recognition = state.speechRecognition;
        state.speechRecognition = null;
        recognition.stop();
    }

    state.speechFinalText = chatInput.value.trim();
    micButton.classList.remove("recording");
    composerNote.textContent = "";
}

async function toggleRecording() {
    if (state.isRecording) {
        stopRecording();
        return;
    }

    unlockAudio();
    stopSpeech();

    const SpeechRecognition = getSpeechRecognition();

    if (!SpeechRecognition) {
        showToast("Live transcription is not supported in this browser.");
        return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    state.speechFinalText = chatInput.value.trim();
    if (state.speechFinalText) {
        state.speechFinalText += " ";
    }

    recognition.onresult = (event) => {
        let interim = "";

        for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;

            if (event.results[i].isFinal) {
                state.speechFinalText += transcript;
            } else {
                interim += transcript;
            }
        }

        chatInput.value = state.speechFinalText + interim;
        autoResizeTextarea();
    };

    recognition.onerror = (event) => {
        if (event.error !== "aborted") {
            showToast("Voice input error: " + event.error);
        }
        stopRecording();
    };

    recognition.onend = () => {
        if (state.isRecording) {
            try {
                recognition.start();
            } catch (_) {
                stopRecording();
            }
        }
    };

    try {
        recognition.start();
        state.speechRecognition = recognition;
        state.isRecording = true;
        micButton.classList.add("recording");
        composerNote.textContent = "Listening… click mic to stop";
        chatInput.focus();
    } catch (_) {
        showToast("Could not start microphone.");
    }
}

emailSubmit.addEventListener("mousedown", unlockAudio);

let authMode = "login"; // login | register
let gateStep = "choose"; // choose | form | otp
let pendingEmail = "";
let pendingPurpose = "login";

function clearSession() {
    state.sessionToken = "";
    state.account = null;
    state.email = "";
    const tenantIdEl = document.getElementById("tenant-id");
    if (tenantIdEl) {
        tenantIdEl.hidden = true;
        tenantIdEl.textContent = "";
    }
}

function applyAccountBranding(account) {
    const widget = account?.widget || {};
    const color = widget.primary_color || "#141414";
    document.documentElement.style.setProperty("--accent", color);

    if (widget.title) {
        document.title = widget.title;
    }

    if (widget.welcome_message && emptyState) {
        const note = emptyState.querySelector(".empty-copy, p");
        if (note) note.textContent = widget.welcome_message;
    }
}

function showGateError(message) {
    gateError.textContent = message;
    gateError.hidden = false;
}

function setGateBusy(busy) {
    emailSubmit.disabled = busy;
    otpResend.disabled = busy;
    tabLogin.disabled = busy;
    tabRegister.disabled = busy;
    authBack.disabled = busy;
}

function showAuthChoose() {
    gateStep = "choose";
    authMode = "login";
    pendingEmail = "";
    pendingPurpose = "login";

    authChoose.classList.remove("hidden");
    authFlow.classList.add("hidden");

    emailInput.value = "";
    emailInput.readOnly = false;
    otpInput.value = "";
    otpStep.classList.add("hidden");
    registerFields.classList.add("hidden");
    emailSubmit.textContent = "Send code";
    gateError.hidden = true;
    gateHint.hidden = false;
}

function openAuthFlow(mode) {
    authMode = mode === "register" ? "register" : "login";
    gateStep = "form";
    pendingPurpose = authMode;

    authChoose.classList.add("hidden");
    authFlow.classList.remove("hidden");

    registerFields.classList.toggle("hidden", authMode !== "register");
    gateLabel.textContent = authMode === "login"
        ? "Login with your email"
        : "Create your company account";
    emailInput.readOnly = false;
    emailInput.value = "";
    otpStep.classList.add("hidden");
    otpInput.value = "";
    emailSubmit.textContent = "Send code";
    gateError.hidden = true;
    gateHint.hidden = false;
    emailInput.focus();
}

function showOtpStep(email, purpose) {
    gateStep = "otp";
    pendingEmail = email;
    pendingPurpose = purpose;

    // Keep Login/Create selection hidden during OTP.
    authChoose.classList.add("hidden");
    authFlow.classList.remove("hidden");

    gateLabel.textContent = `Enter the code sent to ${email}`;
    emailInput.readOnly = true;
    registerFields.classList.add("hidden");
    otpStep.classList.remove("hidden");
    otpInput.value = "";
    emailSubmit.textContent = "Verify";
    gateHint.hidden = true;
    otpInput.focus();
}

function resetGateForm() {
    showAuthChoose();
}

function collectRegisterPayload(email) {
    const company = companyInput.value.trim();

    if (!company) {
        throw new Error("Enter your company name.");
    }

    return {
        email,
        purpose: "register",
        company_name: company,
        custom_prompt: promptInput.value.trim(),
        widget: {
            title: widgetTitleInput.value.trim() || "Knowledge Assistant",
            welcome_message: widgetWelcomeInput.value.trim()
                || "Ask me anything about your documents.",
            primary_color: widgetColorInput.value || "#141414",
            position: widgetPositionInput.value || "bottom-right",
        },
    };
}

async function requestOtp(payload) {
    const response = await fetch(`${API}/api/auth/request-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

    let body = {};
    try {
        body = await response.json();
    } catch (_) {
        body = {};
    }

    if (!response.ok) {
        const detail = body.detail || "Could not send verification code.";
        throw new Error(typeof detail === "string" ? detail : "Could not send verification code.");
    }

    return body;
}

async function verifyOtp(email, otp, purpose) {
    const response = await fetch(`${API}/api/auth/verify-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, otp, purpose }),
    });

    let body = {};
    try {
        body = await response.json();
    } catch (_) {
        body = {};
    }

    if (!response.ok) {
        const detail = body.detail || "Invalid verification code.";
        throw new Error(typeof detail === "string" ? detail : "Invalid verification code.");
    }

    return body;
}

tabLogin.addEventListener("click", () => {
    openAuthFlow("login");
});

tabRegister.addEventListener("click", () => {
    openAuthFlow("register");
});

authBack.addEventListener("click", () => {
    showAuthChoose();
});

emailSubmit.addEventListener("click", async () => {
    unlockAudio();
    gateError.hidden = true;

    if (gateStep === "form") {
        const email = emailInput.value.trim();

        if (!isValidEmail(email)) {
            showGateError("Enter a valid email address.");
            return;
        }

        let payload = { email, purpose: authMode };

        try {
            if (authMode === "register") {
                payload = collectRegisterPayload(email);
            }
        } catch (err) {
            showGateError(err.message);
            return;
        }

        setGateBusy(true);
        emailSubmit.textContent = "Sending…";

        try {
            await requestOtp(payload);
            showOtpStep(email, authMode);
        } catch (err) {
            showGateError(err.message || "Could not send verification code.");
            emailSubmit.textContent = "Send code";
        } finally {
            setGateBusy(false);
        }

        return;
    }

    if (gateStep !== "otp") return;

    const otp = otpInput.value.trim();

    if (!/^\d{6}$/.test(otp)) {
        showGateError("Enter the 6-digit code from your email.");
        return;
    }

    setGateBusy(true);
    emailSubmit.textContent = "Verifying…";

    try {
        const result = await verifyOtp(pendingEmail, otp, pendingPurpose);
        startSession(
            result.account?.email || pendingEmail,
            result.account || null,
            result.session_token || null,
        );
        resetGateForm();
    } catch (err) {
        showGateError(err.message || "Invalid verification code.");
        emailSubmit.textContent = "Verify";
    } finally {
        setGateBusy(false);
    }
});

otpResend.addEventListener("click", async () => {
    if (!pendingEmail) return;

    gateError.hidden = true;
    setGateBusy(true);

    try {
        const payload = pendingPurpose === "register"
            ? collectRegisterPayload(pendingEmail)
            : { email: pendingEmail, purpose: "login" };
        await requestOtp(payload);
        showGateError("A new code was sent.");
        gateError.style.color = "var(--text-secondary)";
        otpInput.focus();
    } catch (err) {
        gateError.style.color = "#b91c1c";
        showGateError(err.message || "Could not resend code.");
    } finally {
        setGateBusy(false);
        setTimeout(() => {
            gateError.style.color = "#b91c1c";
        }, 2500);
    }
});

emailInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") emailSubmit.click();
});

otpInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") emailSubmit.click();
});

sendButton.addEventListener("mousedown", unlockAudio);
sendButton.addEventListener("click", sendMessage);

chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        unlockAudio();
        sendMessage();
    }
});

chatInput.addEventListener("input", autoResizeTextarea);

micButton.addEventListener("mousedown", unlockAudio);
micButton.addEventListener("click", toggleRecording);

fileUpload.addEventListener("change", () => uploadFile(fileUpload.files[0]));

uploadZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadZone.classList.add("dragover");
});

uploadZone.addEventListener("dragleave", () => {
    uploadZone.classList.remove("dragover");
});

uploadZone.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadZone.classList.remove("dragover");
    if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
});

newChatBtn.addEventListener("click", resetConversation);

localStorage.removeItem("ka_email");
localStorage.removeItem("ka_selected_doc");
// Clear any previously persisted auth token from earlier builds.
sessionStorage.removeItem("ka_session_token");
showAuthChoose();

gate.classList.remove("hidden");
app.classList.add("hidden");

