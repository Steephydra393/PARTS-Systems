import os
import sqlite3
import time

DB_FILE = "system_cache.db"


def get_db_connection():
    """Returns a unique database connection for the calling thread."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    return conn


def init_db():
    """Initializes the database schema. Run this once on startup."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Table 1: Master tracking of file hashes
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS file_registry (
            filepath TEXT PRIMARY KEY,
            project TEXT NOT NULL,
            hash TEXT NOT NULL,
            timestamp REAL NOT NULL
        )
    """
    )

    # Table 2: Temporary upload queue cache
    # Storing pending items here ensures data isn't lost if the app restarts mid-run
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS upload_queue (
            filepath TEXT PRIMARY KEY,
            project TEXT NOT NULL,
            hash TEXT NOT NULL,
            timestamp REAL NOT NULL
        )
    """
    )

    conn.commit()
    conn.close()


def process_file_state(filepath: str, project: str, current_hash: str):
    """Checks the database to see if a file is new or modified.

    If it is, updates the registry and adds it to the temp upload queue.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    now = time.time()

    # Check if we have seen this file path before
    cursor.execute(
        "SELECT hash FROM file_registry WHERE filepath = ?", (filepath,)
    )
    row = cursor.fetchone()

    is_changed = False

    if row is None:
        # File is completely new
        is_changed = True
        cursor.execute(
            "INSERT INTO file_registry (filepath, project, hash, timestamp) VALUES (?, ?, ?, ?)",
            (filepath, project, current_hash, now),
        )
    elif row["hash"] != current_hash:
        # File has been modified
        is_changed = True
        cursor.execute(
            "UPDATE file_registry SET hash = ?, timestamp = ? WHERE filepath = ?",
            (current_hash, now, filepath),
        )

    # If new or modified, stage it in our persistent upload queue
    if is_changed:
        cursor.execute(
            """
            INSERT OR REPLACE INTO upload_queue (filepath, project, hash, timestamp)
            VALUES (?, ?, ?, ?)
        """,
            (filepath, project, current_hash, now),
        )
        conn.commit()

    conn.close()
    return is_changed


def get_pending_uploads():
    """Fetches all items currently waiting in the upload queue cache."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT filepath, project, hash, timestamp FROM upload_queue")
    rows = cursor.fetchall()
    conn.close()

    # Convert to standard dictionary list format for the API request
    return [
        {
            "Filename": os.path.basename(r["filepath"]),
            "Fullpath": r["filepath"],  # Kept internally so we know where to read the file from later
            "Project": r["project"],
            "Hash": r["hash"],
            "Timestamp": r["timestamp"],
        }
        for r in rows
    ]


def clear_uploaded_items(filepaths: list):
    """Removes files from the upload queue once the API successfully receives them."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.executemany("DELETE FROM upload_queue WHERE filepath = ?", [(f,) for f in filepaths])
    conn.commit()
    conn.close()