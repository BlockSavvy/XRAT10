from sqlalchemy import Column, Integer, String, Float, DateTime, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from app.core.config import get_settings
import os

settings = get_settings()
Base = declarative_base()

# Set database path based on environment
if os.environ.get('VERCEL_ENV'):
    db_path = "/tmp/analyses.db"
else:
    db_path = "analyses.db"  # Local development path

DATABASE_URL = f"sqlite:///{db_path}"

class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    tweet_id = Column(String, index=True)
    original_text = Column(Text)
    date = Column(DateTime, default=datetime.utcnow)
    total_replies = Column(Integer)
    with_pct = Column(Float)
    against_pct = Column(Float)
    neutral_pct = Column(Float)
    bot_pct = Column(Float)
    notable_quotes = Column(Text)  # Store as JSON string
    response_text = Column(Text)
    engagement_metrics = Column(Text)  # Store as JSON string

    class Config:
        orm_mode = True

# Database setup
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Create tables
if os.environ.get('VERCEL_ENV'):
    # In Vercel, always create tables as they're in /tmp
    Base.metadata.create_all(bind=engine)
else:
    # In development, create tables if they don't exist
    Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 