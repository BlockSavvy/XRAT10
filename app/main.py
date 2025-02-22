from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import tweepy
import asyncio
import json
from datetime import datetime
from typing import Dict, List
import os
import logging
from tweepy import errors as tweepy_errors
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.models import get_db, Analysis
from app.services.sentiment import SentimentAnalyzer
from app.services.bot_detection import BotDetector
from app.services.grok_ai import GrokAI

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title=get_settings().APP_NAME)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure session middleware for serverless
settings = get_settings()
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=3600,  # 1 hour
    same_site="lax",  # Allows OAuth redirects
    https_only=True if not settings.DEBUG else False  # Force HTTPS in production
)

# Helper function to get current user
def get_current_user(request: Request):
    """
    Get the current user from session.
    """
    return request.session.get("user")

# Create event loop for async operations
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

# Initialize services
sentiment_analyzer = SentimentAnalyzer()
bot_detector = BotDetector()
grok_ai = GrokAI()

# X API setup - Move inside a function to avoid startup errors
def get_api_client():
    try:
        if not hasattr(get_api_client, 'api'):
            # Get fresh settings
            settings = get_settings()
            # OAuth 1.0a setup for user context actions
            oauth1_auth = tweepy.OAuthHandler(
                settings.X_API_KEY, 
                settings.X_API_SECRET,
                callback=settings.CALLBACK_URL
            )
            oauth1_auth.set_access_token(
                settings.X_ACCESS_TOKEN, 
                settings.X_ACCESS_TOKEN_SECRET
            )
            get_api_client.api = tweepy.API(oauth1_auth, wait_on_rate_limit=True)
        return get_api_client.api
    except Exception as e:
        print(f"Error initializing X API: {e}")
        return None

def get_client():
    try:
        if not hasattr(get_client, 'client'):
            # Get fresh settings
            settings = get_settings()
            # OAuth 2.0 setup for v2 endpoints
            get_client.client = tweepy.Client(
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
        return get_client.client
    except Exception as e:
        print(f"Error initializing X client: {e}")
        return None

# Update the stream initialization to be lazy
def get_stream():
    if not hasattr(get_stream, 'stream'):
        get_stream.stream = TweetStream(settings.X_BEARER_TOKEN)
    return get_stream.stream

# Only start stream in development
if not os.environ.get('VERCEL_ENV'):
    def start_stream():
        while True:
            try:
                stream = get_stream()
                stream.filter(tweet_fields=["referenced_tweets"])
            except Exception as e:
                print(f"Stream error: {e}")
                continue
    
    # Start stream in background
    import threading
    threading.Thread(target=start_stream, daemon=True).start()

# OAuth routes
@app.get("/auth/twitter")
async def twitter_auth(request: Request):
    """
    Initialize X OAuth authentication.
    """
    try:
        # Get fresh settings
        settings = get_settings()
        
        # Initialize OAuth handler with error handling
        try:
            oauth1_auth = tweepy.OAuthHandler(
                settings.X_API_KEY,
                settings.X_API_SECRET,
                callback=settings.CALLBACK_URL
            )
        except Exception as e:
            logger.error(f"Failed to initialize OAuth handler: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize authentication. Please check API credentials."
            )
        
        # Get the authorization URL with error handling
        try:
            auth_url = oauth1_auth.get_authorization_url(signin_with_twitter=True)
        except Exception as e:
            logger.error(f"Failed to get authorization URL: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to get authorization URL. Please try again."
            )
        
        # Store tokens in session with error handling
        try:
            request.session["oauth_token"] = oauth1_auth.request_token["oauth_token"]
            request.session["oauth_token_secret"] = oauth1_auth.request_token["oauth_token_secret"]
        except Exception as e:
            logger.error(f"Failed to store tokens in session: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to store authentication data. Please try again."
            )
        
        # Redirect to X for authentication
        return RedirectResponse(auth_url, status_code=303)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in twitter_auth: {e}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_code": 500,
                "error_message": "An unexpected error occurred. Please try again later."
            }
        )

@app.get("/callback")
async def callback(request: Request, oauth_token: str = None, oauth_verifier: str = None):
    """
    Handle X OAuth callback.
    """
    try:
        # Get fresh settings
        settings = get_settings()
        
        # Validate OAuth parameters
        if not oauth_token or not oauth_verifier:
            logger.error("Missing OAuth parameters")
            raise HTTPException(status_code=400, detail="Missing OAuth parameters")
        
        # Get stored tokens with error handling
        try:
            stored_token = request.session.get("oauth_token")
            stored_token_secret = request.session.get("oauth_token_secret")
            
            if not stored_token or not stored_token_secret:
                logger.error("No OAuth token found in session")
                raise HTTPException(status_code=400, detail="No OAuth token found in session")
                
            if stored_token != oauth_token:
                logger.error("OAuth token mismatch")
                raise HTTPException(status_code=400, detail="OAuth token mismatch")
        except Exception as e:
            logger.error(f"Session error: {e}")
            raise HTTPException(status_code=400, detail="Session error. Please try logging in again.")
        
        # Initialize OAuth handler
        try:
            oauth1_auth = tweepy.OAuthHandler(
                settings.X_API_KEY,
                settings.X_API_SECRET,
                callback=settings.CALLBACK_URL
            )
            
            oauth1_auth.request_token = {
                "oauth_token": stored_token,
                "oauth_token_secret": stored_token_secret
            }
        except Exception as e:
            logger.error(f"Failed to initialize OAuth handler in callback: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to initialize authentication. Please try again."
            )
        
        try:
            # Get the access token
            access_token = oauth1_auth.get_access_token(oauth_verifier)
            
            # Store the tokens securely
            request.session["access_token"] = access_token[0]
            request.session["access_token_secret"] = access_token[1]
            
            # Initialize API client and verify credentials
            api = tweepy.API(oauth1_auth, wait_on_rate_limit=True)
            user = api.verify_credentials()
            
            # Store user info
            request.session["user"] = {
                "id": user.id,
                "username": user.screen_name,
                "name": user.name,
                "profile_image_url": user.profile_image_url_https
            }
            
            return templates.TemplateResponse(
                "auth_success.html",
                {
                    "request": request,
                    "current_user": request.session["user"]
                }
            )
            
        except tweepy.TweepError as e:
            logger.error(f"Tweepy error in callback: {e}")
            raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in callback: {e}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_code": 500,
                "error_message": "An unexpected error occurred during authentication."
            }
        )

class TweetStream(tweepy.StreamingClient):
    def __init__(self, bearer_token, **kwargs):
        super().__init__(bearer_token, **kwargs)
        self.client = get_client()  # Store v2 client reference

    def on_tweet(self, tweet):
        # Use v2 API to check mentions
        try:
            author = tweet.author_id
            user = self.client.get_user(id=author)
            if user and f"@{user.data.username}" in tweet.text:
                asyncio.run_coroutine_threadsafe(analyze_and_reply(tweet.id), loop)
        except Exception as e:
            print(f"Error in on_tweet: {e}")

    def on_error(self, status_code):
        print(f"Stream Error: {status_code}")
        if status_code == 420:  # Rate limit
            return False
        return True

async def analyze_thread(api, tweet_id: str) -> Dict:
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
        
    except (tweepy_errors.NotFound, tweepy_errors.Forbidden) as e:
        raise HTTPException(status_code=404, detail="Tweet not found or not accessible")
    except tweepy_errors.TooManyRequests as e:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later")
    except tweepy_errors.TweepyException as e:
        raise HTTPException(status_code=400, detail=f"Error analyzing thread: {str(e)}")

async def post_reply(api, tweet_id: str, response_text: str):
    """
    Post a reply with analysis results.
    """
    try:
        # Post reply
        api.update_status(
            status=response_text,
            in_reply_to_status_id=tweet_id,
            auto_populate_reply_metadata=True
        )
        
        return response_text
        
    except tweepy_errors.Forbidden as e:
        logger.error(f"Permission error posting reply: {e}")
        return None
    except tweepy_errors.TooManyRequests as e:
        logger.error("Rate limit exceeded when posting reply")
        return None
    except tweepy_errors.TweepyException as e:
        logger.error(f"Error posting reply: {e}")
        return None

async def analyze_and_reply(tweet_id: str):
    """
    Analyze a tweet and post a reply.
    """
    try:
        api = get_api_client()
        if not api:
            raise HTTPException(status_code=503, detail="API client not available")

        analysis_results = await analyze_thread(api, tweet_id)
        await post_reply(api, tweet_id, analysis_results["original_text"])
    except Exception as e:
        logger.error(f"Error in analyze_and_reply: {e}")

# Webapp routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "current_user": get_current_user(request)
    })

@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    """
    Render login page.
    """
    return templates.TemplateResponse("login.html", {
        "request": request,
        "current_user": get_current_user(request)
    })

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """
    Render dashboard page.
    """
    # Mock data for initial implementation
    stats = {
        "total_analyses": 0,
        "follower_growth": 0,
        "engagement_rate": 0,
        "avg_bot_percentage": 0
    }
    recent_analyses = []
    grok_insights = []
    sentiment_dates = []
    sentiment_positive = []
    sentiment_negative = []
    engagement_dates = []
    engagement_rates = []
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "current_user": get_current_user(request),
        "stats": stats,
        "recent_analyses": recent_analyses,
        "grok_insights": grok_insights,
        "sentiment_dates": sentiment_dates,
        "sentiment_positive": sentiment_positive,
        "sentiment_negative": sentiment_negative,
        "engagement_dates": engagement_dates,
        "engagement_rates": engagement_rates
    })

@app.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    """
    Render settings page.
    """
    # Mock data for initial implementation
    connected_accounts = []
    grok_api_key = os.getenv("XAI_API_KEY", "")
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "current_user": get_current_user(request),
        "connected_accounts": connected_accounts,
        "grok_api_key": grok_api_key
    })

@app.post("/analyze")
async def analyze(request: Request, tweet_id: str = Form(...)):
    try:
        logging.info(f"Starting analysis for tweet {tweet_id}")
        
        # Initialize clients
        api_client = get_api_client()
        grok_client = GrokAI()
        
        if not api_client:
            raise HTTPException(status_code=401, detail="API client not available")
            
        # Analyze thread
        thread_analysis = await analyze_thread(api_client, tweet_id)
        logging.info("Thread analysis completed")
        
        # Get Grok insights
        grok_insights = await grok_client.analyze_thread(
            thread_analysis["original_text"],
            thread_analysis.get("replies", [])  # Use get() with default empty list
        )
        logging.info("Grok analysis completed")
        
        # Generate enhanced response
        enhanced_response = await grok_client.enhance_response(
            thread_analysis["sentiment_stats"],
            thread_analysis.get("tone", "neutral")
        )
        logging.info("Response enhancement completed")
        
        # Store analysis in database
        analysis = Analysis(
            tweet_id=tweet_id,
            original_text=thread_analysis["original_text"],
            date=datetime.now(),
            sentiment_positive=thread_analysis["sentiment_stats"]["percentages"]["with"],
            sentiment_negative=thread_analysis["sentiment_stats"]["percentages"]["against"],
            sentiment_neutral=thread_analysis["sentiment_stats"]["percentages"]["neutral"],
            engagement_likes=thread_analysis["sentiment_stats"].get("engagement", {}).get("likes", 0),
            engagement_replies=thread_analysis["sentiment_stats"].get("engagement", {}).get("replies", 0),
            engagement_retweets=thread_analysis["sentiment_stats"].get("engagement", {}).get("retweets", 0),
            grok_insights=json.dumps(grok_insights),
            enhanced_response=enhanced_response,
            bot_percentage=thread_analysis.get("bot_percentage", 0.0)
        )
        
        db = next(get_db())  # Get database session
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        logging.info("Analysis stored in database")
        
        # Post reply if requested
        if request.query_params.get("post_reply", "false").lower() == "true":
            await post_reply(api_client, tweet_id, enhanced_response)
            logging.info("Reply posted successfully")
        
        return templates.TemplateResponse(
            "results.html",
            {
                "request": request,
                "current_user": get_current_user(request),
                "analysis": analysis,
                "grok_insights": grok_insights,
                "enhanced_response": enhanced_response
            }
        )
        
    except tweepy_errors.NotFound:
        logging.error(f"Tweet {tweet_id} not found")
        raise HTTPException(status_code=404, detail="Tweet not found")
    except tweepy_errors.Forbidden:
        logging.error("Access to tweet forbidden")
        raise HTTPException(status_code=403, detail="Access forbidden")
    except tweepy_errors.TooManyRequests:
        logging.error("Rate limit exceeded")
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

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
        
        avg_with = sum(a.sentiment_positive for a in analyses) / total_analyses
        avg_against = sum(a.sentiment_negative for a in analyses) / total_analyses
        avg_neutral = sum(a.sentiment_neutral for a in analyses) / total_analyses
        avg_bot = sum(a.bot_percentage for a in analyses) / total_analyses
        
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    ) 