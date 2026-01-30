from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from obllomov.schema.orm import Base


DATABASE_URL = "sqlite:///./chat_sessions.db" 
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def get_db():
    if SessionLocal is None:
        raise RuntimeError("Database connection not initialized")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
