import sqlite3
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime
from contextlib import contextmanager

# Database file path
DB_FILE = Path("simulations.db")


@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize the database and create tables if they don't exist"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS simulations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key TEXT UNIQUE NOT NULL,
                topic TEXT NOT NULL,
                topic_id TEXT NOT NULL,
                chapter TEXT NOT NULL,
                chapter_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                level INTEGER NOT NULL,
                simulation_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER DEFAULT 0
            )
        """)
        
        # Create indexes for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cache_key 
            ON simulations(cache_key)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_subject_level 
            ON simulations(subject_id, level)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_topic 
            ON simulations(topic_id, chapter_id, subject_id, level)
        """)


def insert_simulation(
    cache_key: str,
    topic: str,
    topic_id: str,
    chapter: str,
    chapter_id: str,
    subject: str,
    subject_id: str,
    level: int,
    simulation_type: str,
    file_path: str
) -> int:
    """Insert a new simulation record into the database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO simulations (
                cache_key, topic, topic_id, chapter, chapter_id,
                subject, subject_id, level, simulation_type, file_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cache_key, topic, topic_id, chapter, chapter_id,
            subject, subject_id, level, simulation_type, file_path
        ))
        
        return cursor.lastrowid


def get_simulation_by_cache_key(cache_key: str) -> Optional[Dict]:
    """Get simulation record by cache key"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM simulations WHERE cache_key = ?
        """, (cache_key,))
        
        row = cursor.fetchone()
        if row:
            # Update access statistics
            cursor.execute("""
                UPDATE simulations 
                SET accessed_at = CURRENT_TIMESTAMP,
                    access_count = access_count + 1
                WHERE cache_key = ?
            """, (cache_key,))
            
            return dict(row)
        
        return None


def get_all_simulations(
    limit: Optional[int] = None,
    offset: int = 0,
    subject_id: Optional[str] = None,
    level: Optional[int] = None
) -> List[Dict]:
    """Get all simulation records with optional filtering"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        query = "SELECT * FROM simulations WHERE 1=1"
        params = []
        
        if subject_id:
            query += " AND subject_id = ?"
            params.append(subject_id)
        
        if level is not None:
            query += " AND level = ?"
            params.append(level)
        
        query += " ORDER BY created_at DESC"
        
        if limit:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        
        cursor.execute(query, params)
        
        return [dict(row) for row in cursor.fetchall()]


def get_simulation_count(
    subject_id: Optional[str] = None,
    level: Optional[int] = None
) -> int:
    """Get total count of simulations with optional filtering"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        query = "SELECT COUNT(*) as count FROM simulations WHERE 1=1"
        params = []
        
        if subject_id:
            query += " AND subject_id = ?"
            params.append(subject_id)
        
        if level is not None:
            query += " AND level = ?"
            params.append(level)
        
        cursor.execute(query, params)
        
        return cursor.fetchone()["count"]


def delete_simulation_by_cache_key(cache_key: str) -> bool:
    """Delete a simulation record by cache key"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM simulations WHERE cache_key = ?
        """, (cache_key,))
        
        return cursor.rowcount > 0


def delete_all_simulations() -> int:
    """Delete all simulation records and return count of deleted records"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as count FROM simulations")
        count = cursor.fetchone()["count"]
        
        cursor.execute("DELETE FROM simulations")
        
        return count


def get_statistics() -> Dict:
    """Get database statistics"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_simulations,
                COUNT(DISTINCT subject_id) as unique_subjects,
                COUNT(DISTINCT level) as unique_levels,
                SUM(access_count) as total_accesses,
                AVG(access_count) as avg_accesses_per_simulation
            FROM simulations
        """)
        
        stats = dict(cursor.fetchone())
        
        # Get most accessed simulations
        cursor.execute("""
            SELECT topic, subject, level, access_count
            FROM simulations
            ORDER BY access_count DESC
            LIMIT 5
        """)
        
        stats["most_accessed"] = [dict(row) for row in cursor.fetchall()]
        
        return stats


def search_simulations(
    search_term: str,
    search_fields: List[str] = None
) -> List[Dict]:
    """Search simulations by topic, chapter, or subject"""
    if search_fields is None:
        search_fields = ["topic", "chapter", "subject"]
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        conditions = " OR ".join([f"{field} LIKE ?" for field in search_fields])
        query = f"SELECT * FROM simulations WHERE {conditions} ORDER BY created_at DESC"
        
        search_pattern = f"%{search_term}%"
        params = [search_pattern] * len(search_fields)
        
        cursor.execute(query, params)
        
        return [dict(row) for row in cursor.fetchall()]


def get_simulations_by_subject_and_level(subject_id: str, level: int) -> List[Dict]:
    """Get all simulations for a specific subject and level"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM simulations 
            WHERE subject_id = ? AND level = ?
            ORDER BY chapter_id, topic_id
        """, (subject_id, level))
        
        return [dict(row) for row in cursor.fetchall()]


# Initialize database on module import
init_db()