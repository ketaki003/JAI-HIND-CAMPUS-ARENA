import sqlite3

def setup_chat_database():
    # This automatically creates a file named 'chatbot_history.db' in your folder if it doesn't exist
    connection = sqlite3.connect("chatbot_history.db")
    
    # The cursor allows us to execute SQL commands
    cursor = connection.cursor()
    
    # Create the table structure to store chat logs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create an index on session_id to ensure fast lookups during long conversations
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_session ON messages(session_id)")
    
    # Commit saves the changes permanently to the disk file
    connection.commit()
    connection.close()
    print("Database and indexing initialized successfully.")

if __name__ == "__main__":
    setup_chat_database()