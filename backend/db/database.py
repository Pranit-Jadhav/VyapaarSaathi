from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL or DATABASE_URL == "postgresql://user:password@localhost:5432/voicetrace":
    # Temporary fallback to SQLite for easier demo if Postgres is not configured
    DATABASE_URL = "sqlite:///./voicetrace.db"
    print("WARNING: DATABASE_URL not configured. Falling back to SQLite.")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
