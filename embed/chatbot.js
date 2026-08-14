(function () {
    "use strict";

    if (window.__KnowledgeAssistantEmbedLoaded) return;
    window.__KnowledgeAssistantEmbedLoaded = true;

    // Production FastAPI origin. Override with data-api for local/staging.
    var DEFAULT_API_BASE = "http://92.4.88.188:8000";
    var DEFAULT_COLOR = "#141414";
    var DEFAULT_POSITION = "bottom-right";

    var script = document.currentScript;
    var apiBase = resolveApiBase(script);

    if (!apiBase) {
        console.error(
            "[Knowledge Assistant] Could not resolve API base. " +
                'Set data-api to your FastAPI URL (example: data-api="http://92.4.88.188:8000").'
        );
        return;
    }

    apiBase = apiBase.replace(/\/$/, "");

    var apiOrigin = "";
    try {
        apiOrigin = new URL(apiBase).origin;
    } catch (_) {
        apiOrigin = apiBase;
    }

    var brandingKey = "ka_embed_branding:" + apiBase;

    var config = {
        title: "Knowledge Assistant",
        primary_color: DEFAULT_COLOR,
        position: DEFAULT_POSITION,
    };

    restoreBranding();

    function resolveApiBase(el) {
        var explicit = el && el.getAttribute("data-api");
        if (explicit && explicit.trim()) {
            return explicit.trim().replace(/\/$/, "");
        }

        var src = el && el.src;
        if (src) {
            try {
                var url = new URL(src, window.location.href);
                // Never treat the CDN/GitHub host as the Knowledge Assistant API.
                if (
                    /(?:^|\.)jsdelivr\.net$/i.test(url.hostname) ||
                    /(?:^|\.)githubusercontent\.com$/i.test(url.hostname) ||
                    /(?:^|\.)github\.com$/i.test(url.hostname)
                ) {
                    return DEFAULT_API_BASE;
                }
                return url.origin;
            } catch (_) {
                /* fall through */
            }
        }

        return DEFAULT_API_BASE;
    }

    function sanitizeColor(value) {
        var color = String(value || "").trim();
        return /^#[0-9a-fA-F]{6}$/.test(color) ? color : DEFAULT_COLOR;
    }

    function sanitizePosition(value) {
        var position = String(value || "").trim().toLowerCase();
        return position === "bottom-left" ? "bottom-left" : DEFAULT_POSITION;
    }

    function applyBranding(widget) {
        if (!widget || typeof widget !== "object") return;

        if (widget.title) {
            config.title = String(widget.title).slice(0, 80);
        }

        config.primary_color = sanitizeColor(widget.primary_color);
        config.position = sanitizePosition(widget.position);

        try {
            localStorage.setItem(
                brandingKey,
                JSON.stringify({
                    title: config.title,
                    primary_color: config.primary_color,
                    position: config.position,
                })
            );
        } catch (_) {
            /* private mode / blocked storage */
        }

        applyStyles();
        button.setAttribute(
            "aria-label",
            (opened ? "Close " : "Open ") + config.title
        );
    }

    function restoreBranding() {
        try {
            var raw = localStorage.getItem(brandingKey);
            if (!raw) return;
            var saved = JSON.parse(raw);
            if (saved && typeof saved === "object") {
                if (saved.title) config.title = String(saved.title).slice(0, 80);
                config.primary_color = sanitizeColor(saved.primary_color);
                config.position = sanitizePosition(saved.position);
            }
        } catch (_) {
            /* ignore */
        }
    }

    function sideCss(position) {
        if (position === "bottom-left") {
            return "left:24px;right:auto;";
        }
        return "right:24px;left:auto;";
    }

    function sideCssCompact(position) {
        if (position === "bottom-left") {
            return "left:16px;right:auto;";
        }
        return "right:16px;left:auto;";
    }

    function applyStyles() {
        var side = sideCss(config.position);
        var sideCompact = sideCssCompact(config.position);
        var color = sanitizeColor(config.primary_color);
        style.textContent =
            "#knowledge-chat-button{" +
            "position:fixed;" + side + "bottom:24px;width:56px;height:56px;" +
            "border-radius:50%;border:none;background:" + color + ";color:#fff;" +
            "font-size:24px;cursor:pointer;z-index:2147483000;" +
            "display:flex;align-items:center;justify-content:center;" +
            "box-shadow:0 8px 24px rgba(0,0,0,.18);line-height:1;padding:0;" +
            "}" +
            "#knowledge-chat-button:hover{opacity:.9;}" +
            "#knowledge-chat-frame{" +
            "position:fixed;" + side + "bottom:92px;width:460px;height:640px;" +
            "max-width:calc(100vw - 32px);max-height:calc(100vh - 120px);" +
            "border:1px solid #e4e4e0;border-radius:16px;z-index:2147483000;" +
            "box-shadow:0 12px 40px rgba(0,0,0,.18);background:#f4f4f2;overflow:hidden;" +
            "}" +
            "@media (max-width:480px){" +
            "#knowledge-chat-frame{right:8px;left:8px;width:auto;bottom:84px;height:min(640px,calc(100vh - 100px));}" +
            "#knowledge-chat-button{" + sideCompact + "bottom:16px;}" +
            "}";
    }

    var button = document.createElement("button");
    button.type = "button";
    button.id = "knowledge-chat-button";
    button.setAttribute("aria-label", "Open " + config.title);
    button.innerHTML = "💬";
    document.body.appendChild(button);

    var style = document.createElement("style");
    document.head.appendChild(style);
    applyStyles();

    var opened = false;

    // Receive public branding from /widget after Login / Create Account (session-scoped).
    window.addEventListener("message", function (event) {
        if (!event || event.origin !== apiOrigin) return;

        var data = event.data;
        if (!data || data.source !== "knowledge-assistant" || data.type !== "widget-config") {
            return;
        }

        // Reject anything that looks like secrets / prompts.
        if (data.custom_prompt != null || (data.widget && data.widget.custom_prompt != null)) {
            return;
        }

        applyBranding(data.widget || {});
    });

    button.addEventListener("click", function () {
        var existing = document.getElementById("knowledge-chat-frame");

        if (opened && existing) {
            existing.remove();
            opened = false;
            button.setAttribute("aria-label", "Open " + config.title);
            return;
        }

        // iframe loads FastAPI /widget — Login/Create Account + OTP run on the VPS.
        // Tenant is determined by the authenticated session after OTP, never by the CDN script.
        var iframe = document.createElement("iframe");
        iframe.id = "knowledge-chat-frame";
        iframe.title = config.title;
        iframe.allow = "microphone; autoplay";
        iframe.src = apiBase + "/widget";
        document.body.appendChild(iframe);

        opened = true;
        button.setAttribute("aria-label", "Close " + config.title);
    });
})();
