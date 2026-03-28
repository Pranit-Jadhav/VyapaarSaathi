import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

load_dotenv()

def create_database():
    db_url = os.getenv("DATABASE_URL")
    if not db_url or "sqlite" in db_url:
        print("Using SQLite or DATABASE_URL not set. Skipping Postgres DB creation.")
        return

    # Parse connection string to connect to 'postgres' default DB
    # format: postgresql://user:pass@host:port/dbname
    try:
        base_url = db_url.rsplit('/', 1)[0] + '/postgres'
        db_name = db_url.rsplit('/', 1)[1]
        
        print(f"Connecting to {base_url} to create {db_name}...")
        conn = psycopg2.connect(base_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        cur.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{db_name}'")
        exists = cur.fetchone()
        if not exists:
            print(f"Creating database {db_name}...")
            cur.execute(f"CREATE DATABASE {db_name}")
            print("Database created successfully.")
        else:
            print(f"Database {db_name} already exists.")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error creating database: {e}")
        print("Please create the database manually if this failed: CREATE DATABASE voicetrace;")

if __name__ == "__main__":
    create_database()
