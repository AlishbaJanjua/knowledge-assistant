# Deploy (simple)

This app is FastAPI + the custom frontend/widget. Deploy the **whole project** (not just the JS file).

## 1. Local (unchanged)

```bash
python run.py
```

Open: http://127.0.0.1:8000

Embed on any local page:

```html
<script
  src="http://127.0.0.1:8000/embed/chatbot.js"
  data-api="http://127.0.0.1:8000"
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

Replace with your live HTTPS URL:

```html
<script
  src="https://YOUR-DOMAIN/embed/chatbot.js"
  data-api="https://YOUR-DOMAIN"
></script>
```

That one script gives the floating chat button, widget UI, upload, documents, delete, voice in/out, and chat — same features as locally.

## 5. Host tip

On Render/Railway/Fly: connect the GitHub repo, set the two API keys, use the Dockerfile, and attach a persistent volume at `/data` if available.
