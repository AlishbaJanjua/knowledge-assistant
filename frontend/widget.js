(function () {
    "use strict";

    const API_URL = window.location.origin;

    const state = {
        email: "",
        // In-memory only for testing: refresh returns to login.
        sessionToken: "",
        account: null,
        selectedDocument: null,
        documents: [],
        listening: false,
        recognition: null,
        currentAudio: null,
    };

    const emailGate = document.getElementById("emailGate");
    const app = document.getElementById("app");
    const authChoose = document.getElementById("authChoose");
    const authFlow = document.getElementById("authFlow");
    const authBack = document.getElementById("authBack");
    const tabLogin = document.getElementById("tabLogin");
    const tabRegister = document.getElementById("tabRegister");
    const registerFields = document.getElementById("registerFields");
    const companyInput = document.getElementById("companyInput");
    const promptInput = document.getElementById("promptInput");
    const widgetTitleInput = document.getElementById("widgetTitleInput");
    const widgetWelcomeInput = document.getElementById("widgetWelcomeInput");
    const widgetColorInput = document.getElementById("widgetColorInput");
    const widgetPositionInput = document.getElementById("widgetPositionInput");
    const emailInput = document.getElementById("email");
    const emailError = document.getElementById("emailError");
    const continueBtn = document.getElementById("continueBtn");
    const gateLabel = document.getElementById("gateLabel");
    const gateHint = document.getElementById("gateHint");
    const otpStep = document.getElementById("otpStep");
    const otpInput = document.getElementById("otpInput");
    const otpResend = document.getElementById("otpResend");
    const documentsEl = document.getElementById("documents");
    const docEmpty = document.getElementById("docEmpty");
    const docTitle = document.getElementById("docTitle");
    const messages = document.getElementById("messages");
    const emptyState = document.getElementById("emptyState");
    const chunkInfo = document.getElementById("chunk-info");
    const questionInput = document.getElementById("question");
    const sendBtn = document.getElementById("sendBtn");
    const micBtn = document.getElementById("micBtn");
    const fileUpload = document.getElementById("fileUpload");
    const uploadZone = document.getElementById("uploadZone");
    const userEmailEl = document.getElementById("userEmail");
    const composerNote = document.getElementById("composerNote");
    const openSidebarBtn = document.getElementById("openSidebar");
    const closeSidebarBtn = document.getElementById("closeSidebar");
    const sidebarBackdrop = document.getElementById("sidebarBackdrop");

    function isValidEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    }

    async function apiFetch(path, options = {}) {
        let response;
        const headers = { ...(options.headers || {}) };

        if (state.sessionToken) {
            headers["X-Session-Token"] = state.sessionToken;
        }

        try {
            response = await fetch(`${API_URL}${path}`, {
                ...options,
                headers,
            });
        } catch (_) {
            throw new Error("Cannot reach the Knowledge Assistant server.");
        }

        if (!response.ok) {
            let detail = "Something went wrong.";
            try {
                const body = await response.json();
                detail = body.detail || detail;
            } catch (_) {}

            if (response.status === 401) {
                state.sessionToken = "";
            }

            throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
        }

        return response.json();
    }

    function setComposerEnabled(enabled) {
        questionInput.disabled = !enabled;
        sendBtn.disabled = !enabled;
        micBtn.disabled = !enabled;
    }

    function openSidebar() {
        document.body.classList.add("sidebar-open");
        if (sidebarBackdrop) sidebarBackdrop.hidden = false;
    }

    function closeSidebar() {
        document.body.classList.remove("sidebar-open");
        if (sidebarBackdrop) sidebarBackdrop.hidden = true;
    }

    function showStrategy(strategy) {
        if (!chunkInfo) return;

        if (!strategy) {
            chunkInfo.innerHTML = "";
            return;
        }

        chunkInfo.innerHTML = `
            <div class="strategy-card">
                <p class="strategy-label">Recommended chunking strategy</p>
                <p class="strategy-name">${escapeHtml(strategy)}</p>
            </div>
        `;
    }

    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text == null ? "" : String(text);
        return div.innerHTML;
    }

    function clearMessages(placeholder) {
        messages.innerHTML = "";
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.id = "emptyState";
        empty.innerHTML = `<p>${escapeHtml(placeholder || "Upload a document and ask me anything about it.")}</p>`;
        messages.appendChild(empty);
    }

    function addMessage(text, role) {
        const existingEmpty = messages.querySelector(".empty-state");
        if (existingEmpty) existingEmpty.remove();

        const wrapper = document.createElement("div");
        wrapper.className = `message ${role === "user" ? "user" : "assistant"}`;

        const bubble = document.createElement("div");
        bubble.className = "bubble";
        bubble.innerHTML = escapeHtml(text).replace(/\n/g, "<br>");

        wrapper.appendChild(bubble);
        messages.appendChild(wrapper);
        messages.scrollTop = messages.scrollHeight;
        return wrapper;
    }

    function stopSpeech() {
        if (state.currentAudio) {
            state.currentAudio.pause();
            state.currentAudio = null;
        }
    }

    async function playAudioBase64(base64, mimeType) {
        stopSpeech();
        if (!base64) return;

        const binary = atob(base64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }

        const blob = new Blob([bytes], { type: mimeType || "audio/wav" });
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        state.currentAudio = audio;

        audio.onended = () => {
            URL.revokeObjectURL(url);
            if (state.currentAudio === audio) state.currentAudio = null;
            composerNote.textContent = "";
        };

        composerNote.textContent = "Speaking…";
        await audio.play();
    }

    function renderDocuments() {
        documentsEl.innerHTML = "";
        docEmpty.hidden = state.documents.length > 0;

        state.documents.forEach((doc) => {
            const row = document.createElement("div");
            row.className = "doc-row";

            if (doc.document_id === state.selectedDocument) {
                row.classList.add("active");
            }

            const item = document.createElement("button");
            item.type = "button";
            item.className = "doc-item";
            item.textContent = doc.filename;
            item.title = doc.filename;
            item.addEventListener("click", () => selectDocument(doc));

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

            row.appendChild(item);
            row.appendChild(delBtn);
            documentsEl.appendChild(row);
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

            if (state.selectedDocument === doc.document_id) {
                stopSpeech();
                state.selectedDocument = null;
                docTitle.textContent = "Knowledge Assistant";
                showStrategy(null);
                clearMessages("Open the menu to upload a document, then ask anything about it.");
                setComposerEnabled(false);
            }

            await loadDocuments();
        } catch (err) {
            alert(err.message);
        }
    }

    async function loadDocuments() {
        const data = await apiFetch("/api/documents", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: state.email }),
        });

        state.documents = data.documents || [];
        renderDocuments();
    }

    async function selectDocument(doc) {
        state.selectedDocument = doc.document_id;
        docTitle.textContent = doc.filename;
        renderDocuments();
        setComposerEnabled(true);
        closeSidebar();
        await loadHistory();
    }

    async function loadHistory() {
        const data = await apiFetch(
            `/api/history?email=${encodeURIComponent(state.email)}&document_id=${encodeURIComponent(state.selectedDocument)}`
        );

        showStrategy(data.strategy);

        messages.innerHTML = "";

        if (!data.history || data.history.length === 0) {
            clearMessages("Ask me anything about this document.");
            return;
        }

        data.history.forEach((turn) => {
            addMessage(turn.user, "user");
            addMessage(turn.assistant, "assistant");
        });
    }

    async function uploadFile(file) {
        if (!file) return;
        if (!state.email) {
            alert("Enter your email first.");
            return;
        }

        composerNote.textContent = "Uploading…";

        const formData = new FormData();
        formData.append("email", state.email);
        formData.append("file", file);

        try {
            const data = await apiFetch("/api/upload", {
                method: "POST",
                body: formData,
            });

            state.selectedDocument = data.document_id;
            docTitle.textContent = data.filename;
            showStrategy(data.strategy);
            setComposerEnabled(true);

            await loadDocuments();
            clearMessages(`"${data.filename}" is ready. Ask me anything about it.`);
            closeSidebar();
            composerNote.textContent = "";
        } catch (err) {
            alert(err.message);
            composerNote.textContent = "";
        } finally {
            fileUpload.value = "";
        }
    }

    async function sendMessage() {
        const question = questionInput.value.trim();
        if (!question) return;

        if (!state.email) {
            alert("Enter your email first.");
            return;
        }

        if (!state.selectedDocument) {
            alert("Select or upload a document first.");
            openSidebar();
            return;
        }

        questionInput.value = "";
        addMessage(question, "user");
        sendBtn.disabled = true;
        composerNote.textContent = "Thinking…";

        try {
            const data = await apiFetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    email: state.email,
                    document_id: state.selectedDocument,
                    question,
                }),
            });

            addMessage(data.answer, "assistant");

            if (data.audio) {
                await playAudioBase64(data.audio, data.audio_type);
            } else {
                composerNote.textContent = "";
            }
        } catch (err) {
            addMessage(`Error: ${err.message}`, "assistant");
            composerNote.textContent = "";
        } finally {
            sendBtn.disabled = false;
            questionInput.focus();
        }
    }

    function startSession(email, account = null, sessionToken = null) {
        state.email = email;

        if (sessionToken) {
            state.sessionToken = sessionToken;
        }

        if (account) {
            state.account = account;
            // Branding comes from the authenticated account, never from a CDN tenant param.
            applyWidgetBranding(account.widget || {});
        }

        emailGate.classList.add("hidden");
        app.classList.remove("hidden");
        userEmailEl.textContent = account?.company_name
            ? `${account.company_name} · ${email}`
            : email;
        setComposerEnabled(false);
        openSidebar();
        loadDocuments().catch((err) => alert(err.message));
    }

    function contrastTextFor(hex) {
        const color = /^#[0-9a-fA-F]{6}$/.test(hex) ? hex : "#141414";
        const channel = (offset) => parseInt(color.slice(offset, offset + 2), 16) / 255;
        const toLinear = (c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
        const luminance =
            0.2126 * toLinear(channel(1)) +
            0.7152 * toLinear(channel(3)) +
            0.0722 * toLinear(channel(5));
        return luminance > 0.55 ? "#141414" : "#fafafa";
    }

    function applyWidgetBranding(widget) {
        const color = widget.primary_color || "#141414";
        const root = document.documentElement;
        root.style.setProperty("--accent", color);
        root.style.setProperty("--user-bg", color);
        root.style.setProperty("--user-text", contrastTextFor(color));

        if (widget.title) {
            document.title = widget.title;
            docTitle.textContent = widget.title;
        }

        if (widget.welcome_message && emptyState) {
            const note = emptyState.querySelector("p") || emptyState;
            note.textContent = widget.welcome_message;
        }

        // Notify the CDN parent launcher (color/position/title only — never custom_prompt).
        notifyParentBranding(widget);
    }

    function notifyParentBranding(widget) {
        if (!window.parent || window.parent === window) return;

        const safe = {
            title: (widget && widget.title) || "Knowledge Assistant",
            welcome_message:
                (widget && widget.welcome_message) ||
                "Ask me anything about your documents.",
            primary_color: (widget && widget.primary_color) || "#141414",
            position: (widget && widget.position) || "bottom-right",
        };

        try {
            window.parent.postMessage(
                {
                    source: "knowledge-assistant",
                    type: "widget-config",
                    widget: safe,
                },
                "*",
            );
        } catch (_) {
            /* ignore cross-window errors */
        }
    }

    let authMode = "login";
    let gateStep = "choose";
    let pendingEmail = "";
    let pendingPurpose = "login";

    function showGateError(message) {
        emailError.textContent = message;
        emailError.hidden = false;
    }

    function setGateBusy(busy) {
        continueBtn.disabled = busy;
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
        continueBtn.textContent = "Send code";
        emailError.hidden = true;
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
        continueBtn.textContent = "Send code";
        emailError.hidden = true;
        gateHint.hidden = false;
        emailInput.focus();
    }

    function showOtpStep(email, purpose) {
        gateStep = "otp";
        pendingEmail = email;
        pendingPurpose = purpose;

        authChoose.classList.add("hidden");
        authFlow.classList.remove("hidden");

        gateLabel.textContent = `Enter the code sent to ${email}`;
        emailInput.readOnly = true;
        registerFields.classList.add("hidden");
        otpStep.classList.remove("hidden");
        otpInput.value = "";
        continueBtn.textContent = "Verify";
        gateHint.hidden = true;
        otpInput.focus();
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
        const response = await fetch(`${API_URL}/api/auth/request-otp`, {
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
        const response = await fetch(`${API_URL}/api/auth/verify-otp`, {
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

    tabLogin.addEventListener("click", () => openAuthFlow("login"));
    tabRegister.addEventListener("click", () => openAuthFlow("register"));
    authBack.addEventListener("click", () => showAuthChoose());

    continueBtn.addEventListener("click", async () => {
        emailError.hidden = true;

        if (gateStep === "form") {
            const email = emailInput.value.trim();

            if (!isValidEmail(email)) {
                showGateError("Please enter a valid email.");
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
            continueBtn.textContent = "Sending…";

            try {
                await requestOtp(payload);
                showOtpStep(email, authMode);
            } catch (err) {
                showGateError(err.message || "Could not send verification code.");
                continueBtn.textContent = "Send code";
            } finally {
                setGateBusy(false);
            }

            return;
        }

        const otp = otpInput.value.trim();

        if (!/^\d{6}$/.test(otp)) {
            showGateError("Enter the 6-digit code from your email.");
            return;
        }

        setGateBusy(true);
        continueBtn.textContent = "Verifying…";

        try {
            const result = await verifyOtp(pendingEmail, otp, pendingPurpose);
            startSession(
                result.account?.email || pendingEmail,
                result.account || null,
                result.session_token || null,
            );
        } catch (err) {
            showGateError(err.message || "Invalid verification code.");
            continueBtn.textContent = "Verify";
        } finally {
            setGateBusy(false);
        }
    });

    otpResend.addEventListener("click", async () => {
        if (!pendingEmail) return;

        emailError.hidden = true;
        setGateBusy(true);

        try {
            let payload = { email: pendingEmail, purpose: pendingPurpose };
            if (pendingPurpose === "register") {
                payload = collectRegisterPayload(pendingEmail);
            }
            await requestOtp(payload);
            showGateError("A new code was sent.");
            otpInput.focus();
        } catch (err) {
            showGateError(err.message || "Could not resend code.");
        } finally {
            setGateBusy(false);
        }
    });

    emailInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") continueBtn.click();
    });

    otpInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") continueBtn.click();
    });

    // Clear any previously persisted widget auth token from earlier builds.
    sessionStorage.removeItem("ka_widget_session");
    showAuthChoose();

    document.getElementById("loadDocuments").addEventListener("click", () => {
        loadDocuments().catch((err) => alert(err.message));
    });

    openSidebarBtn.addEventListener("click", openSidebar);
    closeSidebarBtn.addEventListener("click", closeSidebar);
    sidebarBackdrop.addEventListener("click", closeSidebar);

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

    sendBtn.addEventListener("click", sendMessage);

    questionInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = "en-US";

        recognition.onresult = (event) => {
            let transcript = "";
            for (let i = event.resultIndex; i < event.results.length; i++) {
                transcript += event.results[i][0].transcript;
            }
            questionInput.value = transcript;
        };

        recognition.onend = () => {
            if (state.listening) {
                try {
                    recognition.start();
                } catch (_) {
                    state.listening = false;
                    micBtn.textContent = "🎙️";
                }
            }
        };

        state.recognition = recognition;
    }

    micBtn.addEventListener("click", () => {
        if (!state.recognition) {
            alert("Speech recognition is not supported in this browser.");
            return;
        }

        stopSpeech();

        if (!state.listening) {
            state.recognition.start();
            state.listening = true;
            micBtn.textContent = "⏹️";
            composerNote.textContent = "Listening…";
        } else {
            state.listening = false;
            state.recognition.stop();
            micBtn.textContent = "🎙️";
            composerNote.textContent = "";
        }
    });
})();
