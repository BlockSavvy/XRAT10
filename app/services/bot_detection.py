from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import re


class BotDetector:
    def __init__(self):
        self.suspicious_patterns = [
            r'buy\s+followers',
            r'earn\s+money\s+fast',
            r'make\s+\$\d+\s+daily',
            r'work\s+from\s+home',
            r'binary\s+options',
            r'crypto\s+investment',
        ]
        
    def analyze_account(self, user_data: Dict) -> Tuple[bool, Dict[str, float]]:
        """
        Analyze a user account for bot-like behavior.
        Returns a tuple of (is_likely_bot, risk_factors).
        """
        risk_factors = {}
        
        # Account age check
        account_age_days = (datetime.now() - user_data["created_at"]).days
        risk_factors["account_age_risk"] = self._calculate_age_risk(account_age_days)
        
        # Tweet frequency check
        tweet_frequency = user_data["statuses_count"] / max(account_age_days, 1)
        risk_factors["tweet_frequency_risk"] = self._calculate_frequency_risk(tweet_frequency)
        
        # Profile completeness check
        profile_completion = self._check_profile_completion(user_data)
        risk_factors["profile_completion_risk"] = 1 - profile_completion
        
        # Follower/Following ratio check
        follower_ratio = user_data["followers_count"] / max(user_data["friends_count"], 1)
        risk_factors["follower_ratio_risk"] = self._calculate_ratio_risk(follower_ratio)
        
        # Default profile check
        risk_factors["default_profile_risk"] = 1.0 if user_data["default_profile"] else 0.0
        
        # Spam pattern check in description
        risk_factors["spam_pattern_risk"] = self._check_spam_patterns(user_data.get("description", ""))
        
        # Calculate overall risk score (weighted average)
        weights = {
            "account_age_risk": 0.2,
            "tweet_frequency_risk": 0.2,
            "profile_completion_risk": 0.15,
            "follower_ratio_risk": 0.15,
            "default_profile_risk": 0.1,
            "spam_pattern_risk": 0.2
        }
        
        overall_risk = sum(risk * weights[factor] for factor, risk in risk_factors.items())
        is_likely_bot = overall_risk > 0.6
        
        return is_likely_bot, risk_factors
    
    def _calculate_age_risk(self, age_days: int) -> float:
        """
        Calculate risk based on account age.
        """
        if age_days < 7:
            return 1.0
        elif age_days < 30:
            return 0.8
        elif age_days < 90:
            return 0.5
        elif age_days < 180:
            return 0.3
        else:
            return 0.1
    
    def _calculate_frequency_risk(self, tweets_per_day: float) -> float:
        """
        Calculate risk based on tweet frequency.
        """
        if tweets_per_day > 100:
            return 1.0
        elif tweets_per_day > 50:
            return 0.8
        elif tweets_per_day > 20:
            return 0.5
        elif tweets_per_day > 10:
            return 0.3
        else:
            return 0.1
    
    def _check_profile_completion(self, user_data: Dict) -> float:
        """
        Check how complete a user's profile is.
        Returns a score between 0 (incomplete) and 1 (complete).
        """
        fields = [
            "name",
            "description",
            "location",
            "profile_image_url",
            "profile_banner_url"
        ]
        
        completed = sum(1 for field in fields if user_data.get(field))
        return completed / len(fields)
    
    def _calculate_ratio_risk(self, follower_ratio: float) -> float:
        """
        Calculate risk based on follower/following ratio.
        """
        if follower_ratio < 0.01:
            return 1.0
        elif follower_ratio < 0.1:
            return 0.8
        elif follower_ratio < 0.5:
            return 0.5
        elif follower_ratio < 1.0:
            return 0.3
        else:
            return 0.1
    
    def _check_spam_patterns(self, text: str) -> float:
        """
        Check for spam patterns in text.
        Returns a risk score between 0 and 1.
        """
        text = text.lower()
        matches = sum(1 for pattern in self.suspicious_patterns if re.search(pattern, text))
        return min(matches / len(self.suspicious_patterns), 1.0)
    
    def analyze_tweet_pattern(self, tweets: List[Dict]) -> Dict[str, float]:
        """
        Analyze tweet patterns for bot-like behavior.
        """
        pattern_metrics = {
            "duplicate_content_ratio": 0.0,
            "api_source_ratio": 0.0,
            "mention_ratio": 0.0,
            "url_ratio": 0.0,
            "timing_regularity": 0.0
        }
        
        if not tweets:
            return pattern_metrics
        
        # Check for duplicate content
        unique_texts = set(tweet["text"] for tweet in tweets)
        pattern_metrics["duplicate_content_ratio"] = 1 - (len(unique_texts) / len(tweets))
        
        # Check source of tweets (api vs. web)
        api_sources = sum(1 for tweet in tweets if "api" in tweet.get("source", "").lower())
        pattern_metrics["api_source_ratio"] = api_sources / len(tweets)
        
        # Check mention and URL patterns
        total_mentions = sum(len(tweet.get("entities", {}).get("user_mentions", [])) for tweet in tweets)
        total_urls = sum(len(tweet.get("entities", {}).get("urls", [])) for tweet in tweets)
        pattern_metrics["mention_ratio"] = total_mentions / len(tweets)
        pattern_metrics["url_ratio"] = total_urls / len(tweets)
        
        # Check timing regularity
        if len(tweets) > 1:
            timestamps = sorted(tweet["created_at"] for tweet in tweets)
            intervals = [(timestamps[i] - timestamps[i-1]).total_seconds() 
                        for i in range(1, len(timestamps))]
            avg_interval = sum(intervals) / len(intervals)
            variance = sum((i - avg_interval) ** 2 for i in intervals) / len(intervals)
            pattern_metrics["timing_regularity"] = 1 / (1 + variance/3600)  # Normalize to 0-1
        
        return pattern_metrics 