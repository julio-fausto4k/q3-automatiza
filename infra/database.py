# infra/database.py
"""SQLite database operations for persistence."""
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from utils.constants import DB_PATH_REVIEWS, DB_PATH_USERS
import bcrypt

class DatabaseManager:
    def __init__(self):
        self.reviews_db_path = Path(DB_PATH_REVIEWS)
        self.users_db_path = Path(DB_PATH_USERS)
    
    def _get_connection(self, db_path: Path) -> sqlite3.Connection:
        """Get database connection."""
        return sqlite3.connect(db_path, check_same_thread=False)
    
    def create_user_sqlite(self, username: str, password: str) -> bool:
        """Create a new user in SQLite database."""
        try:
            conn = self._get_connection(self.users_db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Hash password
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            conn.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", 
                        (username, password_hash))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error creating user: {e}")
            return False
    
    def verify_user(self, username: str, password: str) -> bool:
        """Verify user credentials against SQLite database."""
        try:
            conn = self._get_connection(self.users_db_path)
            cursor = conn.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                stored_hash = row[0]
                return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
            return False
        except Exception as e:
            print(f"Error verifying user: {e}")
            return False
    
    def _init_reviews_db(self) -> sqlite3.Connection:
        """Initialize reviews database."""
        conn = self._get_connection(self.reviews_db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id TEXT PRIMARY KEY,
                merchant_id TEXT,
                created_at TEXT,
                rating REAL,
                comment TEXT,
                reply_text TEXT,
                replied_at TEXT
            )
        """)
        conn.commit()
        return conn
    
    def upsert_reviews(self, merchant_id: str, rows: List[Dict[str, Any]]) -> None:
        """Insert or update reviews in database."""
        if not rows:
            return
        
        conn = self._init_reviews_db()
        cursor = conn.cursor()
        
        for review in rows:
            review_id = review.get("id")
            if not review_id:
                continue
                
            cursor.execute("""
                INSERT INTO reviews (id, merchant_id, created_at, rating, comment)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  merchant_id=excluded.merchant_id,
                  created_at=excluded.created_at,
                  rating=excluded.rating,
                  comment=excluded.comment
            """, (
                review_id,
                merchant_id,
                review.get("created_at", ""),
                review.get("rating", 0),
                review.get("comment", "")
            ))
        
        conn.commit()
        conn.close()
    
    def save_reply_to_db(self, review_id: str, reply_text: str) -> None:
        """Save review reply to database."""
        conn = self._init_reviews_db()
        conn.execute("""
            UPDATE reviews 
            SET reply_text = ?, replied_at = datetime('now') 
            WHERE id = ?
        """, (reply_text, review_id))
        conn.commit()
        conn.close()
    
    def get_reviews(self, merchant_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get reviews from database."""
        conn = self._init_reviews_db()
        query = "SELECT * FROM reviews WHERE merchant_id = ? ORDER BY created_at DESC"
        params = [merchant_id]
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        cursor = conn.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(zip(columns, row)) for row in rows]

# Global database manager instance
db_manager = DatabaseManager()