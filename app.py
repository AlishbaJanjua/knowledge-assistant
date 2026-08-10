import streamlit as st

from graph.workflow import app as agent_graph

from utils.helpers import (
    create_tenant_folder,
    save_uploaded_file,
    register_upload,
    list_uploads,
    sync_registry_from_folder,
)

from loaders.loader import load_document

from agents.chunking_agent import analyze_and_chunk

from vectorstore.chroma_db import (
    create_vectorstore,
    load_vectorstore,
)

from agents.memory_agent import (
    load_memory,
    save_memory,
)

from agents.voice_agent import (
    speech_to_text,
    text_to_speech,
)

def init_session_state():

    defaults = {

        "email": None,

        "history": [],

        "selected_document_id": None,

        "db": None,

        "processed_upload_key": None,

    }


    for key, value in defaults.items():

        if key not in st.session_state:

            st.session_state[key] = value



def select_document(
    email,
    tenant_id,
    document_id
):

    st.session_state.selected_document_id = document_id

    st.session_state.history = load_memory(
        email,
        document_id
    )

    st.session_state.db = load_vectorstore(
        tenant_id,
        document_id
    )



def start_fresh_conversation():

    st.session_state.history = []

    st.session_state.selected_document_id = None

    st.session_state.db = None

    st.session_state.processed_upload_key = None



# -----------------------------
# PAGE CONFIG
# -----------------------------

st.set_page_config(
    page_title="Knowledge Assistant",
    layout="wide",
)

st.markdown("""
<style>

/* ---------- Page ---------- */

.stApp{
    background:#f6f7fb;
}

.main .block-container{
    max-width:1100px;
    padding-top:2.5rem;
    padding-bottom:2rem;
}

/* ---------- Typography ---------- */

h1{
    font-size:2.3rem !important;
    font-weight:700 !important;
    color:#111827;
}

h2,h3{
    color:#111827;
}

/* ---------- Sidebar ---------- */

[data-testid="stSidebar"]{
    background:white;
    border-right:1px solid #ececec;
}

[data-testid="stSidebar"] button{
    border-radius:12px;
}

/* ---------- Buttons ---------- */

.stButton>button{
    border-radius:12px;
    border:none;
    background:#111827;
    color:white;
    font-weight:600;
    transition:.2s;
}

.stButton>button:hover{
    background:#1f2937;
}

/* ---------- File uploader ---------- */

[data-testid="stFileUploader"]{
    border:2px dashed #d1d5db;
    border-radius:16px;
    padding:18px;
    background:white;
}

/* ---------- Chat bubbles ---------- */

[data-testid="stChatMessage"]{
    background:white;
    border-radius:18px;
    padding:18px;
    margin-bottom:14px;
    box-shadow:0 2px 12px rgba(0,0,0,.04);
}

/* User bubble */

[data-testid="stChatMessage"][data-testid*="user"]{
    background:#eef4ff;
}

/* ---------- Chat input ---------- */

[data-testid="stChatInput"]{
    border-radius:18px;
    border:1px solid #dcdcdc;
    background:white;
}

/* ---------- Input boxes ---------- */

.stTextInput input{
    border-radius:12px;
}

/* ---------- Info / Success ---------- */

.stAlert{
    border-radius:14px;
}

/* ---------- Divider ---------- */

hr{
    margin-top:2rem;
    margin-bottom:2rem;
}

/* ---------- Status ---------- */

[data-testid="stStatusWidget"]{
    border-radius:16px;
}

/* ---------- Audio ---------- */

audio{
    width:100%;
}

/* ---------- Mic Button ---------- */

[data-testid="stChatInputMicButton"] svg{
    display:none;
}

[data-testid="stChatInputMicButton"]{
    font-size:1.1rem;
}

[data-testid="stChatInputMicButton"]::before{
    content:"🎙️";
}

/* ---------- Scrollbar ---------- */

::-webkit-scrollbar{
    width:8px;
}

::-webkit-scrollbar-thumb{
    background:#d0d0d0;
    border-radius:20px;
}

/* ---------- Hide Streamlit UI ---------- */

#MainMenu{
    visibility:hidden;
}

header{
    visibility:hidden;
}

footer{
    visibility:hidden;
}

</style>
""", unsafe_allow_html=True)

init_session_state()

st.title("Knowledge Assistant")



# -----------------------------
# EMAIL LOGIN
# -----------------------------

if not st.session_state.email:


    email = st.text_input(
        "Enter your email"
    )


    if st.button(
        "Continue"
    ) and email:


        st.session_state.email = email

        start_fresh_conversation()

        st.rerun()



else:


    email = st.session_state.email


    tenant_id, folder = create_tenant_folder(
        email
    )


    sync_registry_from_folder(
        tenant_id,
        folder
    )


    uploads = list_uploads(
        tenant_id
    )



    if (
        st.session_state.selected_document_id
        and not st.session_state.db
    ):

        select_document(
            email,
            tenant_id,
            st.session_state.selected_document_id
        )



    # -----------------------------
    # SIDEBAR
    # -----------------------------


    with st.sidebar:


        st.success(
            f"Logged in: {email}"
        )


        if st.button(
            "New conversation",
            use_container_width=True
        ):

            start_fresh_conversation()

            st.rerun()



        st.divider()


        st.subheader(
            "Your Documents"
        )



        if not uploads:

            st.caption(
                "No documents uploaded yet."
            )


        else:


            for upload in uploads:


                label = upload["filename"]


                is_selected = (

                    upload["document_id"]

                    == st.session_state.selected_document_id

                )



                if st.button(

                    label,

                    key=f"doc_{upload['document_id']}",

                    use_container_width=True,

                    type="primary"

                    if is_selected

                    else "secondary",

                ):


                    if not is_selected:


                        select_document(

                            email,

                            tenant_id,

                            upload["document_id"],

                        )


                        st.rerun()





    # -----------------------------
    # UPLOAD DOCUMENT
    # -----------------------------


    uploaded_file = st.file_uploader(

        "Upload a Document",

        type=[

            "pdf",

            "docx",

            "txt",

            "csv",

            "pptx",

            "md",

            "html",

        ],

    )



    if uploaded_file:


        upload_key = (

            f"{uploaded_file.name}:"

            f"{uploaded_file.size}"

        )



        if (

            st.session_state.processed_upload_key

            != upload_key

        ):


            path = save_uploaded_file(

                uploaded_file,

                folder

            )


            document_id = register_upload(

                tenant_id,

                uploaded_file.name,

                path

            )



            with st.status(

                "Processing document...",

                expanded=False

            ) as status:



                docs = load_document(
                    path
                )


                status.update(

                    label="Analyzing document...",

                    state="running",

                )



                result = analyze_and_chunk(
                    docs,
                    path,
                )


                chunks = result["chunks"]



                status.update(

                    label="Creating knowledge base...",

                    state="running",

                )



                db = create_vectorstore(

                    chunks,

                    tenant_id,

                    document_id

                )



                status.update(

                    label="Knowledge base ready!",

                    state="complete",

                )



            st.session_state.db = db

            st.session_state.selected_document_id = document_id

            st.session_state.history = []

            st.session_state.processed_upload_key = upload_key



            st.info(

                f"Recommended chunking strategy: **{result['strategy']}** — {result['reason']}"

            )


            st.rerun()





    # -----------------------------
    # CHAT SECTION
    # -----------------------------


    if (

        st.session_state.selected_document_id

        and st.session_state.db

    ):



        selected_upload = next(

            (

                upload

                for upload in uploads

                if upload["document_id"]

                == st.session_state.selected_document_id

            ),

            None,

        )



        doc_label = (

            selected_upload["filename"]

            if selected_upload

            else "Selected document"

        )



        st.divider()



        st.subheader(
            f"Chat: {doc_label}"
        )



        for chat in st.session_state.history:


            with st.chat_message(
                "user"
            ):

                st.write(
                    chat["user"]
                )


            with st.chat_message(
                "assistant"
            ):

                st.write(
                    chat["assistant"]
                )



        # -----------------------------
        # CHAT INPUT (text + voice)
        # -----------------------------

        chat_key = f"chat_input_{st.session_state.selected_document_id}"

        prompt = st.chat_input(
            "Ask something about this document...",
            accept_audio=True,
            key=chat_key,
        )

        question = None

        if prompt:
            if prompt.audio:
                try:
                    with st.spinner("Transcribing..."):
                        transcript = speech_to_text(
                            prompt.audio.getvalue()
                        )
                    st.session_state[chat_key] = transcript
                    st.rerun()
                except Exception as e:
                    st.error(f"Voice input error: {e}")

            elif prompt.text and prompt.text.strip():
                question = prompt.text.strip()

        # -----------------------------
        # PROCESS QUESTION
        # -----------------------------


        if question:

            with st.chat_message("user"):
                st.write(question)



            result = agent_graph.invoke(

                {

                    "question": question,

                    "db": st.session_state.db,

                    "email": email,

                    "document_id":

                    st.session_state.selected_document_id,

                }

            )



            answer = result["answer"]



            with st.chat_message(
                "assistant"
            ):


                st.write(
                    answer
                )


                try:


                    voice = text_to_speech(
                        answer
                    )


                    st.audio(

                        voice,

                        format="audio/mp3",

                        autoplay=True

                    )


                except Exception as e:


                    st.warning(
                        f"Voice generation failed: {e}"
                    )



            save_memory(

                email,

                st.session_state.selected_document_id,

                question,

                answer,

            )



            st.session_state.history.append(

                {

                    "user": question,

                    "assistant": answer,

                }

            )



    elif not uploads:


        st.info(
            "Upload a document to start a new conversation."
        )


    else:


        st.info(

            "Select a document from the sidebar or upload a new one to start chatting."

        )