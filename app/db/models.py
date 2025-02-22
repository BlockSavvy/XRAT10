from sqlalchemy import Column, Integer, String, Float, DateTime, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from app.core.config import get_settings

settings = get_settings()
Base = declarative_base()


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
engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 