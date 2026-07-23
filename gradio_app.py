import gradio as gr
import requests 
import uuid

# Base URL matching your FastAPI backend configuration
API_URL = "http://127.0.0.1:8000/api/chat"
CONVERSATIONS_URL = "http://127.0.0.1:8000/api/conversations"

def get_saved_choices(saved_conversations):
    """Formats saved conversations list into (Title, session_id) tuples for Gradio dropdown."""
    if not saved_conversations:
        return [("No saved chats yet", "")]
    choices = []
    for item in saved_conversations:
        title = item.get("title", "Untitled Chat")
        session_id = item.get("session_id", "")
        choices.append((title, session_id))
    return choices

def fetch_conversations_from_server(user_id):
    """Fetches list of conversation summaries from SQLite via FastAPI gateway."""
    try:
        resp = requests.get(CONVERSATIONS_URL, params={"user_id": user_id or "user1"}, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("conversations", [])
    except Exception:
        pass
    return []

def fetch_single_conversation(session_id, user_id):
    """Fetches individual thread messages for a selected session from FastAPI."""
    try:
        resp = requests.get(f"{CONVERSATIONS_URL}/{session_id}", params={"user_id": user_id or "user1"}, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("messages", [])
    except Exception:
        pass
    return []

def chat_with_college_bot(message, history, selected_model, session_id, user_id, saved_conversations):
    """Sends user query to FastAPI backend and updates active history."""
    dropdown_choices = get_saved_choices(saved_conversations)

    if not message or not str(message).strip():
        safe_history = history or []
        return safe_history, safe_history, session_id, saved_conversations, gr.update(choices=dropdown_choices, value=session_id)

    safe_history = list(history or [])
    safe_history.append({"role": "user", "content": str(message).strip()})

    payload = {
        "question": str(message).strip(),
        "selected_model": selected_model,
        "session_id": session_id,
        "user_id": user_id or "user1",
        "history": safe_history,
    }

    try:
        response = requests.post(API_URL, json=payload, verify=False, timeout=120)

        if response.status_code == 200:
            result = response.json()
            answer = result.get("answer", "No response received.")
        else:
            answer = f"Server Error ({response.status_code}): {response.text}"

    except requests.exceptions.ConnectionError:
        answer = "Connection Failed: Could not connect to the FastAPI backend. Ensure server.py is running on port 8000."
    except Exception as e:
        answer = f"An unexpected error occurred: {str(e)}"

    safe_history.append({"role": "assistant", "content": answer})
    
    # Refresh saved conversations list from database
    updated_saved = fetch_conversations_from_server(user_id) or saved_conversations
    dropdown_choices = get_saved_choices(updated_saved)

    return safe_history, safe_history, session_id, updated_saved, gr.update(choices=dropdown_choices, value=session_id)

def load_selected_conversation(selected_session_id, user_id):
    """Loads historical messages when user toggles a chat from the dropdown."""
    if not selected_session_id:
        return [], [], f"chat-{uuid.uuid4().hex[:8]}"
        
    messages = fetch_single_conversation(selected_session_id, user_id)
    return messages, messages, selected_session_id

def start_new_chat(user_id, saved_conversations):
    """Resets UI view and creates a brand-new session ID."""
    try:
        resp = requests.post("http://127.0.0.1:8000/api/conversations/new", timeout=10)
        if resp.status_code == 200:
            new_session_id = resp.json().get("session_id")
        else:
            new_session_id = f"chat-{uuid.uuid4().hex[:8]}"
    except Exception:
        new_session_id = f"chat-{uuid.uuid4().hex[:8]}"
        
    updated_saved = fetch_conversations_from_server(user_id) or saved_conversations
    dropdown_choices = get_saved_choices(updated_saved)
    
    return [], [], new_session_id, updated_saved, gr.update(choices=dropdown_choices, value="")

with gr.Blocks() as demo:
    gr.Markdown(
        """
        # Jai Hind College Chatbot
        Welcome to the official automated website assistant. Ask questions about courses, admissions, or campus details.
        """
    )

    session_state = gr.State(value=f"chat-{uuid.uuid4().hex[:8]}")
    user_id_state = gr.State(value="user1")
    chat_history_state = gr.State(value=[])
    saved_conversations_state = gr.State(value=[])

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### Sidebar")
            model_dropdown = gr.Dropdown(
                choices=["tinyllama", "qwen2.5:0.5b"],
                value="qwen2.5:0.5b",
                label="Select model",
            )
            user_id_input = gr.State(value=lambda: f"user-{uuid.uuid4().hex[:6]}")
            new_chat_btn = gr.Button("➕ New Chat")
            
            gr.Markdown("#### Saved Conversations")
            saved_chats_dropdown = gr.Dropdown(
                choices=[("No saved chats yet", "")],
                label="Select Chat History",
                interactive=True,
                allow_custom_value=True,
            )

        with gr.Column(scale=3):
            chatbot = gr.Chatbot( height=550)
            text_input = gr.Textbox(
                placeholder="Ask about admissions, courses, fees, or campus info...",
                show_label=False,
            )
            with gr.Row():
                send_btn = gr.Button("Send")
                clear_btn = gr.Button("Clear")

    demo.load(
        fn=lambda user_id: (
            fetch_conversations_from_server(user_id),
            gr.update(choices=get_saved_choices(fetch_conversations_from_server(user_id)), value=""),
        ),
        inputs=[user_id_state],
        outputs=[saved_conversations_state, saved_chats_dropdown]
    )

    send_btn.click(
        chat_with_college_bot,
        inputs=[text_input, chat_history_state, model_dropdown, session_state, user_id_state, saved_conversations_state],
        outputs=[chatbot, chat_history_state, session_state, saved_conversations_state, saved_chats_dropdown],
    ).then(lambda: "", None, text_input)

    text_input.submit(
        chat_with_college_bot,
        inputs=[text_input, chat_history_state, model_dropdown, session_state, user_id_state, saved_conversations_state],
        outputs=[chatbot, chat_history_state, session_state, saved_conversations_state, saved_chats_dropdown],
    ).then(lambda: "", None, text_input)

    saved_chats_dropdown.change(
        load_selected_conversation,
        inputs=[saved_chats_dropdown, user_id_state],
        outputs=[chatbot, chat_history_state, session_state]
    )

    new_chat_btn.click(
        start_new_chat,
        inputs=[user_id_state, saved_conversations_state],
        outputs=[chatbot, chat_history_state, session_state, saved_conversations_state, saved_chats_dropdown],
    )

    clear_btn.click(lambda: ([], []), None, [chatbot, chat_history_state])

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860)