import base64
import logging
import os
import time
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field

from agents.chunking_agent import analyze_and_chunk
from agents.memory_agent import delete_memory, invoke_config, load_memory
from agents.voice_agent import speech_to_text, text_to_speech
from backend.config import CARTESIA_API_KEY
from backend.otp import (
    OTP_REQUEST_COOLDOWN_SECONDS,
    clear_otp,
    cooldown_remaining,
    create_and_store_otp,
    send_otp_email,
    verify_otp,
)
from graph.workflow import app as agent_graph
from loaders.loader import load_document
from tenants.accounts import (
    account_exists,
    create_account,
    get_account_by_email,
    get_account_by_tenant_id,
    public_account_view,
    public_widget_view,
    update_account,
)
from tenants.sessions import create_session_token, verify_session_token
from utils.helpers import (
    create_tenant_folder,
    delete_upload,
    get_document,
    list_uploads,
    register_upload,
    save_file_bytes,
    sync_registry_from_folder,
)
from vectorstore.chroma_db import create_vectorstore, delete_vectorstore, load_vectorstore

AUDIO_MIME = "audio/wav"

logger = logging.getLogger(__name__)

FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "frontend",
)

EMBED_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "embed",
)

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
    ".csv",
    ".pptx",
    ".md",
    ".html",
    ".htm",
}

api = FastAPI(title="Knowledge Assistant API")

api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    email: EmailStr
    document_id: str
    question: str


class EmailRequest(BaseModel):
    email: EmailStr


class DeleteDocumentRequest(BaseModel):
    email: EmailStr
    document_id: str


class SpeakRequest(BaseModel):
    text: str


class WidgetSettings(BaseModel):
    title: Optional[str] = None
    welcome_message: Optional[str] = None
    primary_color: Optional[str] = None
    position: Optional[str] = None


class OtpRequest(BaseModel):
    email: EmailStr
    purpose: str = "login"
    company_name: Optional[str] = None
    custom_prompt: Optional[str] = None
    widget: Optional[WidgetSettings] = None


class OtpVerifyRequest(BaseModel):
    email: EmailStr
    otp: str
    purpose: str = "login"


class AccountUpdateRequest(BaseModel):
    company_name: Optional[str] = None
    custom_prompt: Optional[str] = None
    widget: Optional[WidgetSettings] = None


def _tenant_from_email(email: str):

    tenant_id, folder = create_tenant_folder(email)
    sync_registry_from_folder(tenant_id, folder)
    return tenant_id, folder


def _extract_token(
    authorization: Optional[str],
    x_session_token: Optional[str],
) -> Optional[str]:

    if x_session_token and x_session_token.strip():
        return x_session_token.strip()

    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()

    return None


def require_account(
    authorization: Optional[str] = Header(None),
    x_session_token: Optional[str] = Header(None, alias="X-Session-Token"),
) -> dict:
    """Resolve the authenticated account from the session token only."""

    token = _extract_token(authorization, x_session_token)

    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")

    session = verify_session_token(token)

    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    account = get_account_by_email(session["email"])

    if not account:
        raise HTTPException(status_code=401, detail="Account not found.")

    if account["tenant_id"] != session["tenant_id"]:
        raise HTTPException(status_code=401, detail="Invalid session.")

    return account


def _assert_email_matches_account(account: dict, email: str) -> None:
    if str(email).strip().lower() != account["email"]:
        raise HTTPException(
            status_code=403,
            detail="Email does not match the authenticated account.",
        )


def _speech_payload(text: str) -> dict:

    if not CARTESIA_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="CARTESIA_API_KEY is not configured.",
        )

    try:
        audio = text_to_speech(text)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Voice generation failed: {exc}",
        ) from exc

    return {
        "audio": base64.b64encode(audio).decode("ascii"),
        "audio_type": AUDIO_MIME,
    }


def _otp_error(reason: str) -> HTTPException:
    if reason == "expired":
        return HTTPException(
            status_code=400,
            detail="Code expired or not found. Request a new one.",
        )

    if reason == "locked":
        return HTTPException(
            status_code=400,
            detail="Too many invalid attempts. Request a new code.",
        )

    if reason == "purpose":
        return HTTPException(
            status_code=400,
            detail="Verification code does not match this action. Request a new one.",
        )

    return HTTPException(
        status_code=400,
        detail="Invalid verification code.",
    )


@api.get("/api/health")
def health():

    return {
        "status": "ok",
        "voice": bool(CARTESIA_API_KEY),
    }


@api.post("/api/auth/request-otp")
def request_otp(body: OtpRequest):
    """Send OTP for login or account registration (existing Resend flow)."""

    email = str(body.email).strip().lower()
    purpose = (body.purpose or "login").strip().lower()

    if purpose not in ("login", "register"):
        raise HTTPException(status_code=400, detail="purpose must be login or register.")

    wait = cooldown_remaining(email)

    if wait > 0:
        raise HTTPException(
            status_code=429,
            detail=f"Please wait {wait} seconds before requesting another code.",
        )

    pending = None

    if purpose == "login":
        if not account_exists(email):
            raise HTTPException(
                status_code=404,
                detail="No account found for this email. Please create an account.",
            )
    else:
        if account_exists(email):
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists. Please log in.",
            )

        company_name = (body.company_name or "").strip()

        if not company_name:
            raise HTTPException(status_code=400, detail="Company name is required.")

        pending = {
            "company_name": company_name,
            "custom_prompt": (body.custom_prompt or "").strip(),
            "widget": body.widget.model_dump(exclude_none=True) if body.widget else {},
        }

    otp, expires_in = create_and_store_otp(
        email,
        purpose=purpose,
        pending=pending,
    )

    try:
        send_otp_email(email, otp)
    except Exception as exc:
        clear_otp(email)
        logger.exception("Failed to send OTP email")
        raise HTTPException(
            status_code=502,
            detail="Could not send verification email. Try again shortly.",
        ) from exc

    return {
        "status": "sent",
        "purpose": purpose,
        "expires_in": expires_in,
        "cooldown": OTP_REQUEST_COOLDOWN_SECONDS,
    }


@api.post("/api/auth/verify-otp")
def verify_otp_endpoint(body: OtpVerifyRequest):
    """Verify OTP, then login or create the account and issue a session."""

    email = str(body.email).strip().lower()
    purpose = (body.purpose or "login").strip().lower()

    if purpose not in ("login", "register"):
        raise HTTPException(status_code=400, detail="purpose must be login or register.")

    ok, reason, pending = verify_otp(
        email,
        body.otp,
        expected_purpose=purpose,
    )

    if not ok:
        raise _otp_error(reason)

    if purpose == "login":
        account = get_account_by_email(email)

        if not account:
            raise HTTPException(
                status_code=404,
                detail="No account found for this email. Please create an account.",
            )
    else:
        if not pending or not pending.get("company_name"):
            raise HTTPException(
                status_code=400,
                detail="Registration details expired. Start create-account again.",
            )

        try:
            account = create_account(
                email=email,
                company_name=pending["company_name"],
                custom_prompt=pending.get("custom_prompt") or "",
                widget=pending.get("widget") or {},
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        # Ensure tenant upload folder exists for the new account.
        _tenant_from_email(account["email"])

    token = create_session_token(account["email"], account["tenant_id"])

    return {
        "status": "verified",
        "purpose": purpose,
        "session_token": token,
        "account": public_account_view(account),
    }


@api.get("/api/account/me")
def get_my_account(account: dict = Depends(require_account)):

    return {"account": public_account_view(account)}


@api.put("/api/account/config")
def update_my_account(
    body: AccountUpdateRequest,
    account: dict = Depends(require_account),
):

    try:
        updated = update_account(
            account["email"],
            company_name=body.company_name,
            custom_prompt=body.custom_prompt,
            widget=body.widget.model_dump(exclude_none=True) if body.widget else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"account": public_account_view(updated)}


@api.get("/api/widget-config/{tenant_id}")
def get_widget_config(tenant_id: str):
    """Public widget appearance for embeds (no custom prompt / secrets)."""

    account = get_account_by_tenant_id(tenant_id)

    if not account:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    return public_widget_view(account)


@api.get("/widget")
def chatbot_widget():

    return FileResponse(
        os.path.join(FRONTEND_DIR, "widget.html")
    )


@api.post("/api/documents")
def get_documents(
    body: EmailRequest,
    account: dict = Depends(require_account),
):

    _assert_email_matches_account(account, body.email)
    tenant_id, folder = _tenant_from_email(account["email"])
    uploads = list_uploads(tenant_id)

    return {
        "documents": [
            {
                "document_id": item["document_id"],
                "filename": item["filename"],
                "uploaded_at": item["uploaded_at"],
                "strategy": item.get("chunking_strategy"),
                "reason": item.get("chunking_reason"),
            }
            for item in uploads
        ]
    }


@api.delete("/api/documents")
def remove_document(
    body: DeleteDocumentRequest,
    account: dict = Depends(require_account),
):

    _assert_email_matches_account(account, body.email)
    tenant_id, _ = _tenant_from_email(account["email"])
    deleted = delete_upload(tenant_id, body.document_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found.")

    delete_memory(account["email"], body.document_id)
    delete_vectorstore(tenant_id, body.document_id)

    return {
        "status": "deleted",
        "document_id": body.document_id,
        "filename": deleted.get("filename"),
    }


@api.get("/api/history")
def get_history(
    email: EmailStr = Query(...),
    document_id: str = Query(...),
    account: dict = Depends(require_account),
):

    _assert_email_matches_account(account, email)
    tenant_id, _ = _tenant_from_email(account["email"])
    history = load_memory(account["email"], document_id)
    doc = get_document(tenant_id, document_id)

    return {
        "history": history,
        "strategy": doc.get("chunking_strategy") if doc else None,
        "reason": doc.get("chunking_reason") if doc else None,
    }


@api.post("/api/upload")
async def upload_document(
    email: EmailStr = Form(...),
    file: UploadFile = File(...),
    account: dict = Depends(require_account),
):

    _assert_email_matches_account(account, email)
    extension = os.path.splitext(file.filename or "")[1].lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {extension}",
        )

    tenant_id, folder = _tenant_from_email(account["email"])
    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="Empty file.")

    path = save_file_bytes(content, file.filename, folder)

    upload_started = time.perf_counter()

    step_started = time.perf_counter()
    docs = load_document(path)
    load_elapsed = time.perf_counter() - step_started

    step_started = time.perf_counter()
    result = analyze_and_chunk(docs, path)
    analyze_elapsed = time.perf_counter() - step_started

    document_id = register_upload(
        tenant_id,
        file.filename,
        path,
        strategy=result["applied_strategy"],
        reason=result["reason"],
    )

    step_started = time.perf_counter()
    create_vectorstore(result["chunks"], tenant_id, document_id)
    vectorstore_elapsed = time.perf_counter() - step_started

    total_elapsed = time.perf_counter() - upload_started
    summary = (
        f"[timing] upload_pipeline total={total_elapsed:.3f}s | "
        f"load_document={load_elapsed:.3f}s | "
        f"analyze_and_chunk={analyze_elapsed:.3f}s | "
        f"create_vectorstore={vectorstore_elapsed:.3f}s | "
        f"file={file.filename} chunks={result['chunk_count']} "
        f"strategy={result['applied_strategy']}"
    )
    logger.info(summary)
    print(summary, flush=True)

    return {
        "document_id": document_id,
        "filename": file.filename,
        "strategy": result["applied_strategy"],
        "recommended_strategy": result["recommended_strategy"],
        "applied_strategy": result["applied_strategy"],
        "reason": result["reason"],
        "chunk_count": result["chunk_count"],
        "fallback": result.get("fallback", False),
    }


@api.post("/api/chat")
def chat(
    body: ChatRequest,
    account: dict = Depends(require_account),
):

    _assert_email_matches_account(account, body.email)
    tenant_id, _ = _tenant_from_email(account["email"])
    db = load_vectorstore(tenant_id, body.document_id)

    if not db:
        raise HTTPException(
            status_code=404,
            detail="Document knowledge base not found.",
        )

    result = agent_graph.invoke(
        {
            "question": body.question,
            "email": account["email"],
            "document_id": body.document_id,
            "company_name": account.get("company_name") or "",
            "custom_prompt": account.get("custom_prompt") or "",
        },
        config=invoke_config(account["email"], body.document_id),
    )

    answer = result["answer"]

    speech = _speech_payload(answer)

    return {
        "answer": answer,
        **speech,
    }


@api.post("/api/speak")
def speak(body: SpeakRequest):

    text = body.text.strip()

    if not text:
        raise HTTPException(status_code=400, detail="Empty text.")

    speech = _speech_payload(text)
    audio = base64.b64decode(speech["audio"])

    return Response(content=audio, media_type=AUDIO_MIME)


@api.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)):

    audio_bytes = await file.read()

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file.")

    try:
        text = speech_to_text(audio_bytes)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"text": text}


if os.path.isdir(EMBED_DIR):
    api.mount(
        "/embed",
        StaticFiles(directory=EMBED_DIR),
        name="embed",
    )

if os.path.isdir(FRONTEND_DIR):
    api.mount(
        "/",
        StaticFiles(directory=FRONTEND_DIR, html=True),
        name="frontend",
    )
