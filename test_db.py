import sqlite3
import uuid

DB_FILE = "chatbot_history.db"

def add_message(session_id, role, text):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, role, text)
    )
    conn.commit()
    conn.close()

def fetch_history(session_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Fetch the last 4 rows for this session ID
    cursor.execute(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 4",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

# Simulate a unique session tracking ID (UID)
mock_session_id = str(uuid.uuid4())

print(f"Generated new User Session ID: {mock_session_id}")

# Simulate writing a quick back-and-forth interaction
add_message(mock_session_id, "user", "Hello, can you help me read this scraped text?")
add_message(mock_session_id, "assistant", "Sure! Send over the details.")

# Verify retrieval works correctly
saved_history = fetch_history(mock_session_id)
print("\nRetrieved history rows from SQLite:")
for role, content in reversed(saved_history):
    print(f"[{role}]: {content}")