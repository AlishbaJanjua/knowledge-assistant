# Deployment Guide

This guide explains how to deploy the Knowledge Assistant on an Ubuntu VPS and make the chatbot available through a CDN embed link.

The current deployment uses:

- Oracle Cloud Infrastructure
- Ubuntu 24.04
- Python virtual environment
- FastAPI
- Uvicorn
- systemd
- iptables
- GitHub
- jsDelivr CDN

---

# 1. Project Requirements

The deployment requires:

- An Ubuntu VPS
- Python 3.12+
- Git
- Internet access
- A public IP address
- Port `8000` accessible from the internet

The entire project must be deployed to the server.

Do not deploy only the `embed/chatbot.js` file because the widget communicates with the FastAPI backend.

---

# 2. Clone the Repository

SSH into the VPS and clone the repository:

```bash
git clone https://github.com/AlishbaJanjua/knowledge-assistant.git
cd knowledge-assistant
```

---

# 3. Create the Python Virtual Environment

Create a virtual environment:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Upgrade pip:

```bash
python -m pip install --upgrade pip
```

Install the project dependencies:

```bash
pip install -r requirements.txt
```

---

# 4. Environment Variables

Create a `.env` file in the project root:

```bash
nano .env
```

Add the required environment variables:

```env
GROQ_API_KEY=your_groq_api_key
CARTESIA_API_KEY=your_cartesia_api_key
DATA_DIR=/data
PORT=8000
RELOAD=false
```

Save the file.

### Important

Never commit `.env` or API keys to GitHub.

The `.env` file should remain on the server only.

---

# 5. Configure Oracle Cloud Networking

The Oracle Cloud VCN must allow incoming TCP traffic on port `8000`.

Create an ingress rule with:

```text
Source: 0.0.0.0/0
Protocol: TCP
Destination Port: 8000
```

SSH also needs port `22` to remain accessible.

The server should have:

```text
Internet Gateway
      ↓
Route Table
      ↓
VCN / Subnet
      ↓
Ubuntu VPS
```

---

# 6. Configure the Linux Firewall

If `ufw` is not installed, iptables can be used directly.

Allow TCP port `8000`:

```bash
sudo iptables -C INPUT -p tcp --dport 8000 -j ACCEPT 2>/dev/null || \
sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT
```

Install persistent iptables support:

```bash
sudo DEBIAN_FRONTEND=noninteractive apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent
```

Save the firewall rules:

```bash
sudo netfilter-persistent save
```

This makes the port rule persistent across server reboots.

---

# 7. Test the FastAPI Application

Before creating the permanent service, test that the backend starts correctly.

From the project directory:

```bash
source .venv/bin/activate
```

Start Uvicorn without the development reloader:

```bash
RELOAD=false .venv/bin/uvicorn backend.api:api \
  --host 0.0.0.0 \
  --port 8000 \
  --timeout-keep-alive 300
```

The server should show:

```text
Uvicorn running on http://0.0.0.0:8000
```

Open another SSH session and test:

```bash
curl http://127.0.0.1:8000/
```

The backend should return the Knowledge Assistant frontend.

Test the private IP:

```bash
curl http://10.0.0.127:8000/
```

Test the public endpoint from another machine:

```bash
curl http://YOUR_PUBLIC_IP:8000/
```

---

# 8. Run the Application as a Systemd Service

Running `python run.py` directly inside an SSH session is not suitable for a persistent deployment because the process can stop when the SSH session ends.

Create a systemd service:

```bash
sudo tee /etc/systemd/system/knowledge-assistant.service >/dev/null <<'EOF'
[Unit]
Description=Knowledge Assistant (FastAPI)
After=network.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/knowledge-assistant
Environment=PATH=/home/ubuntu/knowledge-assistant/.venv/bin:/usr/bin
Environment=RELOAD=false
Environment=PORT=8000
EnvironmentFile=-/home/ubuntu/knowledge-assistant/.env
ExecStart=/home/ubuntu/knowledge-assistant/.venv/bin/uvicorn backend.api:api --host 0.0.0.0 --port 8000 --timeout-keep-alive 300
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
```

Reload systemd:

```bash
sudo systemctl daemon-reload
```

Enable the service so it starts automatically after reboot:

```bash
sudo systemctl enable knowledge-assistant.service
```

Start the service:

```bash
sudo systemctl start knowledge-assistant.service
```

Or enable and start it at the same time:

```bash
sudo systemctl enable --now knowledge-assistant.service
```

---

# 9. Verify the Systemd Service

Check the service:

```bash
sudo systemctl status knowledge-assistant.service --no-pager
```

The expected status is:

```text
Active: active (running)
```

Check that port `8000` is listening:

```bash
sudo ss -lntp | grep :8000
```

Expected output should contain:

```text
0.0.0.0:8000
```

Test locally:

```bash
curl -sS -o /dev/null -w "LOCAL_HTTP=%{http_code}\n" \
http://127.0.0.1:8000/
```

Expected:

```text
LOCAL_HTTP=200
```

Test through the private IP:

```bash
curl -sS -o /dev/null -w "PRIVATE_HTTP=%{http_code}\n" \
http://10.0.0.127:8000/
```

Expected:

```text
PRIVATE_HTTP=200
```

Test from another computer:

```bash
curl.exe -sS -m 10 -o NUL -w "PUBLIC_HTTP=%{http_code}`n" http://YOUR_PUBLIC_IP:8000/
```

Expected:

```text
PUBLIC_HTTP=200
```

---

# 10. Check Application Logs

If the service fails or restarts unexpectedly, check the logs:

```bash
sudo journalctl -u knowledge-assistant.service -n 80 --no-pager
```

Follow the logs live:

```bash
sudo journalctl -u knowledge-assistant.service -f
```

---

# 11. Useful Systemd Commands

Check status:

```bash
sudo systemctl status knowledge-assistant.service
```

Start:

```bash
sudo systemctl start knowledge-assistant.service
```

Stop:

```bash
sudo systemctl stop knowledge-assistant.service
```

Restart:

```bash
sudo systemctl restart knowledge-assistant.service
```

Enable at boot:

```bash
sudo systemctl enable knowledge-assistant.service
```

Disable at boot:

```bash
sudo systemctl disable knowledge-assistant.service
```

View logs:

```bash
sudo journalctl -u knowledge-assistant.service
```

---

# 12. CDN Embed

The chatbot widget is available as a JavaScript file through jsDelivr.

### CDN URL

```text
https://cdn.jsdelivr.net/gh/AlishbaJanjua/knowledge-assistant/embed/chatbot.js
```

The widget can be integrated into another website using:

```html
<script
    src="https://cdn.jsdelivr.net/gh/AlishbaJanjua/knowledge-assistant/embed/chatbot.js"
    data-api="http://YOUR_PUBLIC_IP:8000">
</script>
```

For the current internship deployment:

```html
<script
    src="https://cdn.jsdelivr.net/gh/AlishbaJanjua/knowledge-assistant/embed/chatbot.js"
    data-api="http://92.4.88.188:8000">
</script>
```

---

# 13. How the CDN Embed Works

The CDN only hosts the JavaScript widget.

The actual Knowledge Assistant application remains on the VPS.

```text
External Website
       │
       ▼
jsDelivr CDN
       │
       ▼
embed/chatbot.js
       │
       ▼
Oracle Cloud VPS
       │
       ▼
FastAPI /widget
       │
       ▼
Knowledge Assistant
```

The website owner only needs to add the script tag.

The website does not need the Python application, LangChain code, vector store, or other backend files.

---

# 14. Testing the CDN Embed

Create a simple HTML page:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Knowledge Assistant CDN Test</title>
</head>
<body>

    <h1>Test Website</h1>
    <p>This website is testing the Knowledge Assistant CDN embed.</p>

    <script
        src="https://cdn.jsdelivr.net/gh/AlishbaJanjua/knowledge-assistant/embed/chatbot.js"
        data-api="http://92.4.88.188:8000">
    </script>

</body>
</html>
```

Open the page in a browser.

The Knowledge Assistant chat button should appear.

Clicking the button should open the chatbot widget and connect to the FastAPI backend on the VPS.

---

# 15. Important Deployment Notes

### The VPS must remain available

The chatbot backend runs on the Oracle Cloud VPS.

The user's own computer does not need to remain connected to the VPS.

The application continues running through systemd even after the SSH session is closed.

### The GitHub repository contains the application code

The VPS runs a cloned copy of the GitHub repository.

If the application code changes, pull the changes on the VPS:

```bash
cd ~/knowledge-assistant
git pull
```

After code changes, restart the service:

```bash
sudo systemctl restart knowledge-assistant.service
```

### API keys

Never commit API keys to GitHub.

Keep them in the server's `.env` file.

### HTTPS

The current internship/demo deployment uses:

```text
http://92.4.88.188:8000
```

A production deployment should use HTTPS and a custom domain.

HTTPS is especially important when embedding the chatbot into HTTPS websites because browsers can block HTTP backend requests as mixed content.

---

# 16. Current Deployment

The current Knowledge Assistant deployment is:

```text
GitHub Repository
    │
    ▼
Oracle Cloud Ubuntu VPS
    │
    ├── Python Virtual Environment
    │
    ├── FastAPI
    │
    ├── Uvicorn
    │
    └── systemd
          │
          ▼
    Port 8000
          │
          ▼
http://92.4.88.188:8000
```

The CDN widget is:

```text
https://cdn.jsdelivr.net/gh/AlishbaJanjua/knowledge-assistant/embed/chatbot.js
```

The chatbot has been tested successfully on an external website using the CDN embed script.

---

## Deployment Status

- ✅ Project deployed to Oracle Cloud VPS
- ✅ Python virtual environment configured
- ✅ Dependencies installed
- ✅ Environment variables configured
- ✅ Oracle Cloud port 8000 configured
- ✅ iptables port 8000 rule configured
- ✅ Persistent firewall rules configured
- ✅ FastAPI backend running on Uvicorn
- ✅ systemd service configured
- ✅ Automatic restart enabled
- ✅ Automatic startup after reboot enabled
- ✅ Public backend access verified
- ✅ CDN widget available through jsDelivr
- ✅ External website CDN integration tested
