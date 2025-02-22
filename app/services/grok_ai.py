import os
import httpx
from typing import List, Dict, Any

class GrokAI:
    def __init__(self):
        self.api_key = os.getenv("XAI_API_KEY")
        self.base_url = "https://api.grok.x.ai/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def analyze_thread(self, original_tweet: str, replies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze a thread using Grok AI for deeper insights.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/analyze",
                headers=self.headers,
                json={
                    "original_tweet": original_tweet,
                    "replies": [reply["text"] for reply in replies]
                }
            )
            return response.json()

    async def generate_insights(self, analysis_results: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Generate human-readable insights from analysis results.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/insights",
                headers=self.headers,
                json=analysis_results
            )
            insights = response.json()["insights"]
            return [
                {
                    "title": insight["title"],
                    "description": insight["description"]
                }
                for insight in insights
            ]

    async def enhance_response(self, stats: Dict[str, Any], tone: str) -> str:
        """
        Use Grok to enhance response with more engaging language.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/enhance",
                headers=self.headers,
                json={
                    "stats": stats,
                    "tone": tone,
                    "style": "witty"
                }
            )
            return response.json()["response"] 