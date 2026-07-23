# test_db.py
import sqlite3
import uuid

DB_FILE = "chatbot_history.db"

def add_chat_turn(user_id, session_id, question, answer):
    """Simulates saving a combined question & answer turn."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (user_id, session_id, question, answer) VALUES (?, ?, ?, ?)",
        (user_id, session_id, question, answer)
    )
    conn.commit()
    conn.close()

def fetch_history(user_id, session_id):
    """Simulates reading context for a specific user and session."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT question, answer FROM messages WHERE user_id = ? AND session_id = ? ORDER BY id DESC LIMIT 2",
        (user_id, session_id)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

# Run a quick test simulation
mock_user_id = "user_a1b2c3"
mock_session_id = f"chat-{uuid.uuid4().hex[:8]}"

print(f"Testing Profile -> User ID: {mock_user_id} | Session ID: {mock_session_id}")

# Add test entry
add_chat_turn(
    user_id=mock_user_id,
    session_id=mock_session_id,
    question="Where is the college located?",
    answer="We are situated right on A Road in Churchgate, South Mumbai!"
)

# Fetch test entry
saved_history = fetch_history(mock_user_id, mock_session_id)
print("\nRetrieved history turns from SQLite:")
for question, answer in reversed(saved_history):
    print(f"[Question]: {question}")
    print(f"[Answer]: {answer}")
    print("-" * 30)