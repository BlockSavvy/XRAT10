from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import tweepy
import asyncio
import json
from datetime import datetime
from typing import Dict, List

from app.core.config import get_settings
from app.db.models import get_db, Analysis
from app.services.sentiment import SentimentAnalyzer
from app.services.bot_detection import BotDetector

# Initialize FastAPI app
app = FastAPI(title=get_settings().APP_NAME)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Initialize services
settings = get_settings()
sentiment_analyzer = SentimentAnalyzer()
bot_detector = BotDetector()

# X API setup
try:
    # OAuth 1.0a setup for user context actions (posting tweets, etc)
    oauth1_auth = tweepy.OAuthHandler(
        settings.X_API_KEY, 
        settings.X_API_SECRET,
        callback=settings.CALLBACK_URL
    )
    oauth1_auth.set_access_token(
        settings.X_ACCESS_TOKEN, 
        settings.X_ACCESS_TOKEN_SECRET
    )
    api = tweepy.API(oauth1_auth, wait_on_rate_limit=True)

    # OAuth 2.0 setup for v2 endpoints
    client = tweepy.Client(
        bearer_token=settings.X_BEARER_TOKEN,
        consumer_key=settings.X_API_KEY,
        consumer_secret=settings.X_API_SECRET,
        access_token=settings.X_ACCESS_TOKEN,
        access_token_secret=settings.X_ACCESS_TOKEN_SECRET,
        client_id=settings.CLIENT_ID,
        client_secret=settings.CLIENT_SECRET,
        callback=settings.CALLBACK_URL,
        wait_on_rate_limit=True
    )
except Exception as e:
    print(f"Error initializing X API: {e}")
    api = None
    client = None

# OAuth callback route
@app.get("/callback")
async def callback(request: Request, oauth_token: str = None, oauth_verifier: str = None):
    try:
        # Get the access token and secret
        oauth1_auth.request_token = {'oauth_token': oauth_token,
                                   'oauth_token_secret': oauth_verifier}
        oauth1_auth.get_access_token(oauth_verifier)
        
        # Store the tokens (in a real app, save these securely)
        access_token = oauth1_auth.access_token
        access_token_secret = oauth1_auth.access_token_secret
        
        return templates.TemplateResponse(
            "auth_success.html",
            {"request": request}
        )
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_code": 400,
                "error_message": f"Authentication failed: {str(e)}"
            }
        )

class TweetStream(tweepy.StreamingClient):
    def __init__(self, bearer_token, **kwargs):
        super().__init__(bearer_token, **kwargs)
        self.client = client  # Store v2 client reference

    def on_tweet(self, tweet):
        # Use v2 API to check mentions
        try:
            author = tweet.author_id
            user = client.get_user(id=author)
            if user and f"@{user.data.username}" in tweet.text:
                asyncio.run_coroutine_threadsafe(analyze_and_reply(tweet.id), loop)
        except Exception as e:
            print(f"Error in on_tweet: {e}")

    def on_error(self, status_code):
        print(f"Stream Error: {status_code}")
        if status_code == 420:  # Rate limit
            return False
        return True

async def analyze_thread(tweet_id: str) -> Dict:
    """
    Analyze a thread including the original tweet and its replies.
    """
    try:
        # Get original tweet
        original_tweet = api.get_status(tweet_id, tweet_mode="extended")
        original_text = original_tweet.full_text
        
        # Get replies
        replies = []
        for tweet in tweepy.Cursor(api.search_tweets,
                                 q=f"to:{original_tweet.user.screen_name}",
                                 since_id=tweet_id,
                                 tweet_mode="extended").items(100):
            reply_data = {
                "text": tweet.full_text,
                "author": tweet.user.screen_name,
                "created_at": tweet.created_at,
                "user": {
                    "created_at": tweet.user.created_at,
                    "statuses_count": tweet.user.statuses_count,
                    "followers_count": tweet.user.followers_count,
                    "friends_count": tweet.user.friends_count,
                    "default_profile": tweet.user.default_profile,
                    "description": tweet.user.description
                }
            }
            replies.append(reply_data)
        
        # Analyze sentiment
        sentiment_stats = sentiment_analyzer.analyze_thread(replies)
        
        # Analyze bots
        bot_count = 0
        bot_risk_factors = []
        for reply in replies:
            is_bot, risk_factors = bot_detector.analyze_account(reply["user"])
            if is_bot:
                bot_count += 1
            bot_risk_factors.append(risk_factors)
        
        # Calculate bot percentage
        bot_percentage = (bot_count / len(replies) * 100) if replies else 0
        
        # Combine all stats
        analysis_results = {
            "tweet_id": tweet_id,
            "original_text": original_text,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_replies": len(replies),
            "sentiment_stats": sentiment_stats,
            "bot_percentage": bot_percentage,
            "bot_risk_factors": bot_risk_factors
        }
        
        return analysis_results
        
    except tweepy.TweepError as e:
        raise HTTPException(status_code=400, detail=f"Error analyzing thread: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

async def post_reply(tweet_id: str, analysis_results: Dict):
    """
    Post a reply with analysis results.
    """
    try:
        # Get response tone
        tone = sentiment_analyzer.get_response_tone(analysis_results["sentiment_stats"])
        
        # Craft response based on tone
        response = craft_response(analysis_results, tone)
        
        # Post reply
        api.update_status(
            status=response,
            in_reply_to_status_id=tweet_id,
            auto_populate_reply_metadata=True
        )
        
        return response
    except Exception as e:
        print(f"Error posting reply: {e}")
        return None

def craft_response(analysis_results: Dict, tone: str) -> str:
    """
    Craft a response based on analysis results and tone.
    """
    stats = analysis_results["sentiment_stats"]
    
    # Select intro based on tone
    intros = {
        "celebratory": "The crowd's all in—time to pop the champagne! 🎉",
        "empathetic_firm": "Wow, the haters are out in force. Don't worry, I've got your back! 😏",
        "positive_balanced": "The vibes are good in this thread! Let's break it down. ✨",
        "diplomatic_balanced": "Interesting discussion here. Let me share what I found. ��",
        "neutral_analytical": "Here's an objective analysis of this thread. 📊"
    }
    
    intro = intros.get(tone, intros["neutral_analytical"])
    
    # Format stats
    stats_text = (
        f"Thread Stats:\n"
        f"📊 {analysis_results['total_replies']} replies analyzed\n"
        f"👍 {stats['percentages']['with']:.1f}% positive\n"
        f"👎 {stats['percentages']['against']:.1f}% negative\n"
        f"😐 {stats['percentages']['neutral']:.1f}% neutral\n"
        f"🤖 {analysis_results['bot_percentage']:.1f}% likely bots"
    )
    
    # Add notable quote if available
    quote_text = ""
    if stats["notable_quotes"]:
        quote = stats["notable_quotes"][0]
        sentiment = "💫" if quote["score"] > 0 else "💭"
        quote_text = f"\n\nStandout Take {sentiment}\n@{quote['author']}: '{quote['text'][:100]}...'"
    
    # Add trending keywords if available
    keywords_text = ""
    if stats["keywords"]:
        top_keywords = list(stats["keywords"].items())[:3]
        keywords_text = "\n\nTrending Keywords: " + ", ".join(f"#{k}" for k, _ in top_keywords)
    
    # Combine all parts
    response = f"{intro}\n\n{stats_text}{quote_text}{keywords_text}\n\n#ThreadAnalysis"
    
    # Ensure response is within X's character limit
    if len(response) > 280:
        response = response[:277] + "..."
    
    return response

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    Render home page.
    """
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    tweet_id: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Analyze a thread and store results.
    """
    try:
        # Analyze thread
        analysis_results = await analyze_thread(tweet_id)
        
        # Post reply
        response_text = await post_reply(tweet_id, analysis_results)
        
        # Store analysis in database
        db_analysis = Analysis(
            tweet_id=tweet_id,
            original_text=analysis_results["original_text"],
            date=datetime.now(),
            total_replies=analysis_results["total_replies"],
            with_pct=analysis_results["sentiment_stats"]["percentages"]["with"],
            against_pct=analysis_results["sentiment_stats"]["percentages"]["against"],
            neutral_pct=analysis_results["sentiment_stats"]["percentages"]["neutral"],
            bot_pct=analysis_results["bot_percentage"],
            notable_quotes=json.dumps(analysis_results["sentiment_stats"]["notable_quotes"]),
            response_text=response_text,
            engagement_metrics=json.dumps({"keywords": analysis_results["sentiment_stats"]["keywords"]})
        )
        db.add(db_analysis)
        db.commit()
        
        return templates.TemplateResponse(
            "results.html",
            {
                "request": request,
                "analysis": analysis_results,
                "response_text": response_text
            }
        )
        
    except HTTPException as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_code": e.status_code,
                "error_message": e.detail
            }
        )

@app.get("/past_analyses", response_class=HTMLResponse)
async def past_analyses(request: Request, db: Session = Depends(get_db)):
    """
    View past analyses.
    """
    analyses = db.query(Analysis).order_by(Analysis.date.desc()).all()
    return templates.TemplateResponse(
        "past_analyses.html",
        {"request": request, "analyses": analyses}
    )

@app.get("/api/v1/stats")
async def get_stats(db: Session = Depends(get_db)):
    """
    Get analysis statistics API endpoint.
    """
    try:
        analyses = db.query(Analysis).all()
        total_analyses = len(analyses)
        
        if total_analyses == 0:
            return JSONResponse({
                "total_analyses": 0,
                "average_sentiment": {"with": 0, "against": 0, "neutral": 0},
                "average_bot_percentage": 0
            })
        
        avg_with = sum(a.with_pct for a in analyses) / total_analyses
        avg_against = sum(a.against_pct for a in analyses) / total_analyses
        avg_neutral = sum(a.neutral_pct for a in analyses) / total_analyses
        avg_bot = sum(a.bot_pct for a in analyses) / total_analyses
        
        return JSONResponse({
            "total_analyses": total_analyses,
            "average_sentiment": {
                "with": round(avg_with, 2),
                "against": round(avg_against, 2),
                "neutral": round(avg_neutral, 2)
            },
            "average_bot_percentage": round(avg_bot, 2)
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching stats: {str(e)}")

# Update the stream initialization
if api:
    stream = TweetStream(settings.X_BEARER_TOKEN)
    
    def start_stream():
        while True:
            try:
                stream.filter(tweet_fields=["referenced_tweets"])
            except Exception as e:
                print(f"Stream error: {e}")
                continue
    
    # Start stream in background
    import threading
    threading.Thread(target=start_stream, daemon=True).start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    ) 