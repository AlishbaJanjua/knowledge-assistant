(function () {
    "use strict";

    if (window.__KnowledgeAssistantEmbedLoaded) return;
    window.__KnowledgeAssistantEmbedLoaded = true;

    var script = document.currentScript;
    var tenantId = ((script && script.getAttribute("data-tenant")) || "").trim();
    var apiBase = resolveApiBase(script);

    if (!apiBase) {
        console.error(
            "[Knowledge Assistant] Missing data-api. " +
                "When loading from jsDelivr/CDN you must set data-api to your FastAPI backend URL " +
                '(example: data-api="http://92.4.88.188:8000").'
        );
        return;
    }

    if (!tenantId) {
        console.error(
            "[Knowledge Assistant] Missing data-tenant. " +
                "Set data-tenant to your account tenant_id " +
                "(shown in the Knowledge Assistant sidebar after login)."
        );
        return;
    }

    apiBase = apiBase.replace(/\/$/, "");

    var config = {
        title: "Knowledge Assistant",
        primary_color: "#141414",
        position: "bottom-right",
        welcome_message: "Ask me anything about your documents.",
    };

    function resolveApiBase(el) {
        var explicit = el && el.getAttribute("data-api");
        if (explicit && explicit.trim()) {
            return explicit.trim().replace(/\/$/, "");
        }

        var src = el && el.src;
        if (!src) {
            return "http://127.0.0.1:8000";
        }

        try {
            var url = new URL(src, window.location.href);
            // Never treat the CDN/GitHub host as the Knowledge Assistant API.
            if (
                /(?:^|\.)jsdelivr\.net$/i.test(url.hostname) ||
                /(?:^|\.)githubusercontent\.com$/i.test(url.hostname) ||
                /(?:^|\.)github\.com$/i.test(url.hostname)
            ) {
                return "";
            }
            return url.origin;
        } catch (_) {
            return "http://127.0.0.1:8000";
        }
    }

    function sideCss(position) {
        if (position === "bottom-left") {
            return "left:24px;right:auto;";
        }
        return "right:24px;left:auto;";
    }

    function applyStyles() {
        var side = sideCss(config.position);
        var color = config.primary_color || "#141414";
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
            "#knowledge-chat-button{right:16px;left:auto;bottom:16px;}" +
            "}";
    }

    var button = document.createElement("button");
    button.type = "button";
    button.id = "knowledge-chat-button";
    button.setAttribute("aria-label", "Open Knowledge Assistant");
    button.innerHTML = "💬";
    document.body.appendChild(button);

    var style = document.createElement("style");
    document.head.appendChild(style);
    applyStyles();

    // Public appearance only (title/color/position/welcome). Never fetches prompts/secrets.
    fetch(apiBase + "/api/widget-config/" + encodeURIComponent(tenantId))
        .then(function (res) {
            if (!res.ok) throw new Error("config");
            return res.json();
        })
        .then(function (data) {
            if (data && data.widget) {
                config.title = data.widget.title || config.title;
                config.primary_color = data.widget.primary_color || config.primary_color;
                config.position = data.widget.position || config.position;
                config.welcome_message =
                    data.widget.welcome_message || config.welcome_message;
                button.setAttribute("aria-label", "Open " + config.title);
                applyStyles();
            }
        })
        .catch(function () {
            console.warn(
                "[Knowledge Assistant] Could not load widget config for tenant:",
                tenantId
            );
        });

    var opened = false;

    button.addEventListener("click", function () {
        var existing = document.getElementById("knowledge-chat-frame");

        if (opened && existing) {
            existing.remove();
            opened = false;
            button.setAttribute("aria-label", "Open " + config.title);
            return;
        }

        // iframe loads FastAPI /widget on the VPS — auth/OTP stays inside that origin.
        var iframe = document.createElement("iframe");
        iframe.id = "knowledge-chat-frame";
        iframe.title = config.title;
        iframe.allow = "microphone; autoplay";
        iframe.src =
            apiBase +
            "/widget?tenant=" +
            encodeURIComponent(tenantId);
        document.body.appendChild(iframe);

        opened = true;
        button.setAttribute("aria-label", "Close " + config.title);
    });
})();
