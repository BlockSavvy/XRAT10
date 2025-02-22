from sqlalchemy import Column, Integer, String, Float, DateTime, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from app.core.config import get_settings
import os
import json

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
    original_text = Column(String)
    date = Column(DateTime, default=datetime.now)
    sentiment_positive = Column(Float)
    sentiment_negative = Column(Float)
    sentiment_neutral = Column(Float)
    engagement_likes = Column(Integer)
    engagement_replies = Column(Integer)
    engagement_retweets = Column(Integer)
    grok_insights = Column(String)  # JSON string of Grok AI insights
    enhanced_response = Column(String)  # Enhanced response from Grok
    bot_percentage = Column(Float, default=0.0)

    def to_dict(self):
        return {
            "id": self.id,
            "tweet_id": self.tweet_id,
            "original_text": self.original_text,
            "date": self.date.isoformat(),
            "sentiment": {
                "positive": self.sentiment_positive,
                "negative": self.sentiment_negative,
                "neutral": self.sentiment_neutral
            },
            "engagement": {
                "likes": self.engagement_likes,
                "replies": self.engagement_replies,
                "retweets": self.engagement_retweets
            },
            "grok_insights": json.loads(self.grok_insights) if self.grok_insights else None,
            "enhanced_response": self.enhanced_response,
            "bot_percentage": self.bot_percentage
        }

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