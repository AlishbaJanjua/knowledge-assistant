(function () {
    "use strict";

    if (window.__KnowledgeAssistantEmbedLoaded) return;
    window.__KnowledgeAssistantEmbedLoaded = true;

    var script = document.currentScript;
    var apiBase =
        (script && script.getAttribute("data-api")) ||
        (script && script.src ? new URL(script.src).origin : "http://127.0.0.1:8000");

    apiBase = apiBase.replace(/\/$/, "");

    var button = document.createElement("button");
    button.type = "button";
    button.id = "knowledge-chat-button";
    button.setAttribute("aria-label", "Open Knowledge Assistant");
    button.innerHTML = "💬";
    document.body.appendChild(button);

    var style = document.createElement("style");
    style.textContent =
        "#knowledge-chat-button{" +
        "position:fixed;right:24px;bottom:24px;width:56px;height:56px;" +
        "border-radius:50%;border:none;background:#141414;color:#fff;" +
        "font-size:24px;cursor:pointer;z-index:2147483000;" +
        "display:flex;align-items:center;justify-content:center;" +
        "box-shadow:0 8px 24px rgba(0,0,0,.18);line-height:1;padding:0;" +
        "}" +
        "#knowledge-chat-button:hover{opacity:.9;}" +
        "#knowledge-chat-frame{" +
        "position:fixed;right:24px;bottom:92px;width:460px;height:640px;" +
        "max-width:calc(100vw - 32px);max-height:calc(100vh - 120px);" +
        "border:1px solid #e4e4e0;border-radius:16px;z-index:2147483000;" +
        "box-shadow:0 12px 40px rgba(0,0,0,.18);background:#f4f4f2;overflow:hidden;" +
        "}" +
        "@media (max-width:480px){" +
        "#knowledge-chat-frame{right:8px;left:8px;width:auto;bottom:84px;height:min(640px,calc(100vh - 100px));}" +
        "#knowledge-chat-button{right:16px;bottom:16px;}" +
        "}";

    document.head.appendChild(style);

    var opened = false;

    button.addEventListener("click", function () {
        var existing = document.getElementById("knowledge-chat-frame");

        if (opened && existing) {
            existing.remove();
            opened = false;
            button.setAttribute("aria-label", "Open Knowledge Assistant");
            return;
        }

        var iframe = document.createElement("iframe");
        iframe.id = "knowledge-chat-frame";
        iframe.title = "Knowledge Assistant";
        iframe.allow = "microphone; autoplay";
        iframe.src = apiBase + "/widget";
        document.body.appendChild(iframe);

        opened = true;
        button.setAttribute("aria-label", "Close Knowledge Assistant");
    });
})();
