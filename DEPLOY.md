# Deploy (simple)

This app is FastAPI + the custom frontend/widget. Deploy the **whole project** (not just the JS file).

## 1. Local (unchanged)

```bash
python run.py
```

Open: http://127.0.0.1:8000

Embed on any local page (replace `YOUR_TENANT_ID` with the account tenant id shown after login):

```html
<script
  src="http://127.0.0.1:8000/embed/chatbot.js"
  data-api="http://127.0.0.1:8000"
  data-tenant="YOUR_TENANT_ID"
></script>
```

## 2. Required secrets

Set these on your host:

- `GROQ_API_KEY`
- `CARTESIA_API_KEY`

Optional:

- `PORT` — set automatically on most hosts (Render/Railway)
- `DATA_DIR` — defaults to `/data` in Docker; use a persistent disk if you want uploads to survive redeploys
- `RELOAD=false` — already set in Docker

## 3. Docker

```bash
docker build -t knowledge-assistant .
docker run -p 8000:8000 \
  -e GROQ_API_KEY=... \
  -e CARTESIA_API_KEY=... \
  -v ka-data:/data \
  knowledge-assistant
```

## 4. After deploy — CDN-style embed

jsDelivr serves `embed/chatbot.js` from GitHub. The script must also point at your live FastAPI backend and a tenant id:

```html
<script
  src="https://cdn.jsdelivr.net/gh/AlishbaJanjua/knowledge-assistant@main/embed/chatbot.js"
  data-api="https://YOUR-DOMAIN-OR-VPS:8000"
  data-tenant="YOUR_TENANT_ID"
></script>
```

- `data-api` — FastAPI origin on your VPS/host (not jsDelivr)
- `data-tenant` — company `tenant_id` from the Knowledge Assistant sidebar after login

That one script gives the floating chat button, tenant branding, widget UI, upload, documents, delete, voice in/out, and chat — same features as locally.

## 5. Host tip

On Render/Railway/Fly: connect the GitHub repo, set the two API keys, use the Dockerfile, and attach a persistent volume at `/data` if available.

## 6. Oracle Cloud VPS — open port 8000 (OS firewall)

Opening the **subnet security list** is not enough on Oracle Ubuntu images. The OS `iptables` INPUT chain usually allows SSH (`:22`) and then **REJECT**s everything else — including `:8000`.

Symptoms:
- `curl http://127.0.0.1:8000` on the VPS works
- SSH to the public IP works
- Browser / Windows `curl http://PUBLIC_IP:8000` times out
- `curl http://PUBLIC_IP:8000` **from the VPS itself** may also fail (hairpin); ignore that test

On the VPS, run:

```bash
cd ~/knowledge-assistant
bash scripts/open-port-8000.sh
```

Or manually:

```bash
sudo iptables -L INPUT -n --line-numbers
# Insert BEFORE the REJECT line (replace N with that line number):
sudo iptables -I INPUT N -p tcp --dport 8000 -j ACCEPT
sudo apt-get update && sudo apt-get install -y iptables-persistent
sudo netfilter-persistent save
```

Then retest **from Windows**: `http://YOUR_PUBLIC_IP:8000/`

If it still times out, check the instance VNIC **Network Security Group** in OCI Console for ingress TCP 8000 from `0.0.0.0/0`.
