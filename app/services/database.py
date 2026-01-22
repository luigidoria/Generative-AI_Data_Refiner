import sqlite3
from pathlib import Path


def init_database():
    db_path = Path(__file__).parent.parent.parent / "database" / "transacoes.db"
    schema_path = Path(__file__).parent.parent.parent / "database" / "schema.sql"
    
    if db_path.exists():
        return
    
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    
    conn.commit()
    conn.close()