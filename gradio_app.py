import gradio as gr
import requests

# Base URL matching your FastAPI backend configuration
API_URL = "http://127.0.0.1:8000/api/chat"

def chat_with_college_bot(message, history):
    """
    Sends the user message to the FastAPI server and yields the bot's response.
    """
    if not message.strip():
        return "Please enter a valid question."

    payload = {"question": message}
    
    try:
        # Send POST request to FastAPI endpoint
        # Note: verify=False is added in case your corporate environment blocks internal loopback calls
        response = requests.post(API_URL, json=payload, verify=False)
        
        if response.status_code == 200:
            result = response.json()
            return result.get("answer", "No response received.")
        else:
            return f"⚠️ Server Error ({response.status_code}): {response.text}"
            
    except requests.exceptions.ConnectionError:
        return "❌ Connection Failed: Could not connect to the FastAPI backend. Ensure server.py is running on port 8000."
    except Exception as e:
        return f"❌ An unexpected error occurred: {str(e)}"

# Define a clean, modern UI wrapper using Gradio Blocks
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        """
        # 🎓 Jai Hind College Chatbot
        Welcome to the official automated website assistant. Ask questions about courses, admissions, or campus details.
        """
    )
    
    # Standard ChatInterface for seamless historical conversation layout
    gr.ChatInterface(
        fn=chat_with_college_bot,
        examples=[
            "What courses are offered?", 
            "What are the admission requirements?", 
            "How can I contact the administration?"
        ],
        
    )

if __name__ == "__main__":
    # Launch local server
    demo.launch(server_name="127.0.0.1", server_port=7860)