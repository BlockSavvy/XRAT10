from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from typing import Dict, List, Tuple
import json
import re


class SentimentAnalyzer:
    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()
        
    def analyze_text(self, text: str) -> Dict[str, float]:
        """
        Analyze sentiment of text using VADER.
        Returns detailed sentiment scores.
        """
        return self.analyzer.polarity_scores(text)
    
    def get_sentiment_category(self, compound_score: float) -> str:
        """
        Convert compound score to sentiment category with finer granularity.
        """
        if compound_score >= 0.5:
            return "strongly_positive"
        elif 0.1 <= compound_score < 0.5:
            return "positive"
        elif -0.1 < compound_score < 0.1:
            return "neutral"
        elif -0.5 <= compound_score < -0.1:
            return "negative"
        else:
            return "strongly_negative"
    
    def analyze_thread(self, replies: List[Dict]) -> Dict:
        """
        Analyze sentiment patterns in a thread of replies.
        """
        sentiment_stats = {
            "total_replies": len(replies),
            "sentiment_counts": {
                "strongly_positive": 0,
                "positive": 0,
                "neutral": 0,
                "negative": 0,
                "strongly_negative": 0
            },
            "notable_quotes": [],
            "sentiment_progression": [],
            "keywords": {}
        }
        
        for reply in replies:
            # Analyze sentiment
            scores = self.analyze_text(reply["text"])
            category = self.get_sentiment_category(scores["compound"])
            sentiment_stats["sentiment_counts"][category] += 1
            
            # Track sentiment progression
            sentiment_stats["sentiment_progression"].append({
                "timestamp": reply["created_at"],
                "compound_score": scores["compound"]
            })
            
            # Extract notable quotes (high sentiment intensity)
            if abs(scores["compound"]) > 0.5:
                sentiment_stats["notable_quotes"].append({
                    "text": reply["text"],
                    "author": reply["author"],
                    "score": scores["compound"]
                })
            
            # Extract and count significant keywords
            keywords = self._extract_keywords(reply["text"])
            for keyword in keywords:
                sentiment_stats["keywords"][keyword] = sentiment_stats["keywords"].get(keyword, 0) + 1
        
        # Calculate percentages
        total = sentiment_stats["total_replies"]
        sentiment_stats["percentages"] = {
            "with": ((sentiment_stats["sentiment_counts"]["strongly_positive"] + 
                     sentiment_stats["sentiment_counts"]["positive"]) / total * 100),
            "against": ((sentiment_stats["sentiment_counts"]["strongly_negative"] + 
                        sentiment_stats["sentiment_counts"]["negative"]) / total * 100),
            "neutral": (sentiment_stats["sentiment_counts"]["neutral"] / total * 100)
        }
        
        # Sort keywords by frequency
        sentiment_stats["keywords"] = dict(sorted(
            sentiment_stats["keywords"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:10])
        
        return sentiment_stats
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extract significant keywords from text.
        """
        # Remove mentions, hashtags, and URLs
        text = re.sub(r'@\w+|#\w+|http\S+|https\S+', '', text.lower())
        
        # Split into words and filter common words
        words = text.split()
        common_words = set(['the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i', 'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at'])
        keywords = [word for word in words if word not in common_words and len(word) > 3]
        
        return keywords
    
    def get_response_tone(self, sentiment_stats: Dict) -> str:
        """
        Determine appropriate response tone based on sentiment analysis.
        """
        with_pct = sentiment_stats["percentages"]["with"]
        against_pct = sentiment_stats["percentages"]["against"]
        
        if with_pct > 70:
            return "celebratory"
        elif against_pct > 70:
            return "empathetic_firm"
        elif with_pct > against_pct:
            return "positive_balanced"
        elif against_pct > with_pct:
            return "diplomatic_balanced"
        else:
            return "neutral_analytical" 