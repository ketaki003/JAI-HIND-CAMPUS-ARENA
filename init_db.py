# init_db.py
import sqlite3

def setup_chat_database():
    # Automatically creates 'chatbot_history.db' with the new single-row turn structure
    connection = sqlite3.connect("chatbot_history.db")
    cursor = connection.cursor()
    
    # Create the table structure storing user_id, session_id, question, and answer together
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            chunk TEXT,       
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                   
        )
    """)
    
    # Composite index for ultra-fast lookups by user and session ID
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_session ON messages(user_id, session_id)")
    
    connection.commit()
    connection.close()
    print("Database and multi-user indexing initialized successfully.")

if __name__ == "__main__":
    setup_chat_database()