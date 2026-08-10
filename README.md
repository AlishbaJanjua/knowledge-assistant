# Knowledge Assistant

A multi-agent AI-powered Knowledge Assistant that allows users to upload documents, automatically analyze them, recommend an appropriate chunking strategy, build a knowledge base, and interact with the uploaded content through a chatbot and voice assistant.

The system is built around a modular agent architecture using LangChain and LangGraph concepts, with support for document processing, RAG, conversational memory, voice interaction, and CDN-based website embedding.

---

## 🚀 Features

- 📄 **Document Upload**
  - Upload documents such as PDF and PowerPoint files.
  - Documents are automatically processed and added to the knowledge base.

- 🧠 **Automatic Chunking Recommendation**
  - The system analyzes uploaded documents.
  - It recommends a suitable chunking strategy based on the document structure and content.

- 🔎 **Retrieval-Augmented Generation (RAG)**
  - Uploaded documents are processed into chunks.
  - Embeddings are generated and stored in a vector store.
  - Relevant information is retrieved when answering user questions.

- 🤖 **Multi-Agent Architecture**
  - Specialized agents handle different tasks.
  - Agent-based orchestration is implemented using LangChain and LangGraph concepts.
  - The architecture is modular and can be extended with additional agents.

- 💬 **Chatbot**
  - Interactive web-based chatbot.
  - Supports document-based question answering.
  - Can be embedded into external websites.

- 🎙️ **Voice Assistant**
  - Supports voice-based interaction alongside the chatbot.
  - Uses the same knowledge and agent architecture for conversational interaction.

- 🧠 **Conversational Memory**
  - Supports short-term conversation context.
  - Supports persistent user context and interaction history.

- 👤 **User Personalization**
  - Users can provide their name and email.
  - Previous interaction history can be associated with the user for a personalized experience.

- 🌐 **CDN Embedding**
  - The chatbot widget is hosted through a CDN using jsDelivr.
  - The chatbot can be integrated into another website using a simple `<script>` tag.

- ☁️ **Cloud Deployment**
  - Backend deployed on an Oracle Cloud Ubuntu VPS.
  - FastAPI runs through Uvicorn.
  - Systemd is used to keep the application running and automatically start it after a server reboot.

---

## 🏗️ System Architecture

```text
                         ┌─────────────────────┐
                         │   External Website  │
                         └──────────┬──────────┘
                                    │
                              CDN Embed Script
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   Chatbot Widget    │
                         │     chatbot.js      │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │    FastAPI Backend  │
                         │       /widget       │
                         └──────────┬──────────┘
                                    │
                     ┌──────────────┼──────────────┐
                     │              │              │
                     ▼              ▼              ▼
                Multi-Agent       Memory          RAG
                 System         Management      Pipeline
                     │              │              │
                     └──────────────┼──────────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │     Vector Store    │
                         └─────────────────────┘
```

---

## 📂 Project Structure

```text
knowledge-assistant/
│
├── agents/
│
├── backend/
│   ├── api.py
│   ├── config.py
│   ├── database.py
│   ├── llm.py
│   └── prompts.py
│
├── embed/
│   ├── chatbot.js
│   └── chatbot.css
│
├── embeddings/
│
├── frontend/
│
├── graph/
│
├── loaders/
│
├── tenants/
│
├── utils/
│
├── vectorstore/
│
├── app.py
├── run.py
├── Dockerfile
├── requirements.txt
├── DEPLOY.md
└── README.md
```

---

## 🧰 Tech Stack

### Backend

- Python
- FastAPI
- Uvicorn

### AI / LLM

- LangChain
- LangGraph
- Groq
- Cartesia

### RAG

- Document Loaders
- Text Chunking
- Embeddings
- Chroma
- LangChain Chroma
- Retrieval-Augmented Generation

### Frontend

- HTML
- CSS
- JavaScript

### Deployment

- Oracle Cloud Infrastructure
- Ubuntu 24.04
- systemd
- iptables
- Uvicorn

### CDN

- GitHub
- jsDelivr

---

## 📄 Document Processing Pipeline

```text
Document Upload
      │
      ▼
Document Analysis
      │
      ▼
Chunking Strategy Recommendation
      │
      ▼
Document Chunking
      │
      ▼
Embedding Generation
      │
      ▼
Vector Store
      │
      ▼
Knowledge Base
      │
      ▼
User Query
      │
      ▼
Relevant Context Retrieval
      │
      ▼
LLM Response
```

The system analyzes uploaded documents and recommends an appropriate chunking strategy instead of relying on a single fixed chunking method.

---

## 🤖 Multi-Agent Architecture

The Knowledge Assistant follows a modular agent-based architecture where specialized agents can handle different tasks.

A simplified flow is:

```text
                    User Query
                        │
                        ▼
                 Agent / Graph
                        │
        ┌───────────────┼────────────────┐
        │               │                │
        ▼               ▼                ▼
    RAG Agent       Voice Agent     General Agent
        │               │                │
        └───────────────┼────────────────┘
                        │
                        ▼
                   Final Response
```

The modular architecture allows additional specialized agents to be added without redesigning the entire application.

---

## 🧠 Memory

The Knowledge Assistant supports both short-term and long-term conversational context.

### Short-Term Memory

Short-term memory maintains context during an ongoing conversation, allowing the assistant to understand follow-up questions and references to previous messages.

### Long-Term Memory

Long-term memory allows user information and interaction history to be associated with a user's identity.

When a user provides their name and email, the system can identify previous interactions and use relevant context for a more personalized experience.

---

## 🎙️ Voice and Chatbot

The system supports both text-based chatbot interaction and voice-based interaction.

```text
                    User
                     │
             ┌───────┴───────┐
             │               │
             ▼               ▼
          Chatbot         Voice Bot
             │               │
             └───────┬───────┘
                     │
                     ▼
              Agent System
                     │
                     ▼
               RAG / Memory
                     │
                     ▼
                 Response
```

Both interaction modes are designed to work with the same underlying knowledge and agent architecture.

---

# 🌐 CDN Embed

The chatbot is available as a CDN-hosted JavaScript widget using jsDelivr.

### CDN URL

```text
https://cdn.jsdelivr.net/gh/AlishbaJanjua/knowledge-assistant/embed/chatbot.js
```

### Embed Code

Add the following script to any HTML website:

```html
<script
    src="https://cdn.jsdelivr.net/gh/AlishbaJanjua/knowledge-assistant/embed/chatbot.js"
    data-api="http://92.4.88.188:8000">
</script>
```

The script automatically creates the chatbot widget on the website and connects it to the Knowledge Assistant backend running on the Oracle Cloud VPS.

### CDN Integration Flow

```text
External Website
       │
       ▼
   CDN Script
       │
       ▼
   chatbot.js
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

The CDN embed has been tested on a separate website and successfully loads and communicates with the chatbot.

> **Note:** The current internship/demo deployment uses an HTTP VPS endpoint. A production deployment should use HTTPS and a custom domain.

---

# ☁️ Cloud Deployment

The Knowledge Assistant backend is deployed on an Oracle Cloud Ubuntu VPS.

### Server

```text
Provider: Oracle Cloud Infrastructure
Operating System: Ubuntu 24.04
Architecture: x86_64
Backend Port: 8000
```

### Backend URL

```text
http://92.4.88.188:8000
```

The FastAPI backend is managed using a systemd service so that the application:

- Runs independently of an SSH session
- Automatically restarts if the application stops
- Starts automatically after a VPS reboot
- Uses the project's Python virtual environment
- Loads environment variables from `.env`

---

## 🔐 Environment Variables

The application uses environment variables for API keys and configuration.

Required variables include:

```env
GROQ_API_KEY=your_groq_api_key
CARTESIA_API_KEY=your_cartesia_api_key
DATA_DIR=your_data_directory
PORT=8000
RELOAD=false
```

**Never commit `.env` or API keys to GitHub.**

---

# 🖥️ Local Development

Clone the repository:

```bash
git clone https://github.com/AlishbaJanjua/knowledge-assistant.git
cd knowledge-assistant
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

Activate it on Linux/macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file with the required environment variables.

Run the application:

```bash
python run.py
```

The application will be available at:

```text
http://127.0.0.1:8000
```

---

## 🛠️ Production Service

The application runs on the Oracle Cloud VPS as a systemd service.

Check the service status:

```bash
sudo systemctl status knowledge-assistant.service
```

Restart the application:

```bash
sudo systemctl restart knowledge-assistant.service
```

View application logs:

```bash
sudo journalctl -u knowledge-assistant.service -n 80 --no-pager
```

---

## 🔗 Repository

**GitHub Repository:**

https://github.com/AlishbaJanjua/knowledge-assistant

**CDN Embed:**

https://cdn.jsdelivr.net/gh/AlishbaJanjua/knowledge-assistant/embed/chatbot.js

---

## 🎯 Project Objective

The main objective of this project is to demonstrate the practical implementation of modern LLM application concepts, including:

- Retrieval-Augmented Generation
- LangChain
- LangGraph
- Multi-agent systems
- Document processing
- Intelligent chunking
- Vector search
- Conversational memory
- Voice-based interaction
- Modular agent orchestration
- Cloud deployment
- CDN-based chatbot integration

The architecture is designed to be modular and extensible so that additional agents, memory systems, retrieval methods, and integrations can be added as the project evolves.

---
