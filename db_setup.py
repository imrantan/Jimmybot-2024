import sqlite3
import os

# Create the table first
# Function to create the database connection
def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except sqlite3.Error as e:
        print(e)
    return conn

# Function to create the conversations table
def create_table(conn):
    sql_create_conversations_table = """ 
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY,
        user_id TEXT NOT NULL,
        timestamp DATETIME NOT NULL,
        role TEXT NOT NULL,
        parts TEXT NOT NULL
    );"""
    try:
        c = conn.cursor()
        c.execute(sql_create_conversations_table)
    except sqlite3.Error as e:
        print(e)

# Function to create a new conversation
def create_conversation(conn, conversation):
    sql = ''' INSERT INTO chat_history(user_id, timestamp, role, parts)
              VALUES(?,?,?,?) '''
    cur = conn.cursor()
    cur.execute(sql, conversation)
    conn.commit()
    return cur.lastrowid

# Example conversation data
conversations = {
    "User123": [
        {"timestamp": "2024-03-23T12:00:00", 
         "role": "user", 
         "parts": "Hello! I'm doing well, thank you. How can I assist you today?"},

        {"timestamp": "2024-03-23T12:02:00", 
         "role": "model", 
         "parts": "Sure, I'd be happy to help. What specifically do you need assistance with?"}
    ],
    "User456": [
        {"timestamp": "2024-03-23T13:00:00", 
         "role": "user", 
         "parts": "Briefly explain how a computer works to a young child."},

        {"timestamp": "2024-03-23T13:02:00", 
         "role": "model", 
         "parts": "I don't know."}
    ]
}

# Path to the SQLite database file
database = r"chat_history.db"

def database_initialisation():
     # Check if the database file exists
    if os.path.exists(database):
        # Delete the database file
        os.remove(database)
        print(f"Existing database '{database}' deleted.")

    # Create a database connection
    conn = create_connection(database)
    with conn:
        # Create the conversations table
        create_table(conn)
        print("Table 'chat_history' created successfully.")

        # Iterate through each user's conversation
        for user_id, user_conversations in conversations.items():
            # Insert each conversation into the database
            for conv in user_conversations:
                conversation = (user_id, conv["timestamp"], conv["role"], conv["parts"])
                create_conversation(conn, conversation)
            print(f"Conversations for user {user_id} inserted into the database.")
