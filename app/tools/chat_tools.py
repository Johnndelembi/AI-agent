import os
import json
import re
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from langgraph.types import Command, interrupt

from app.config import settings
from app.services.model_service import model_service
from app.services.tts_service import tts_service
from app.services.news_service import news_service
from app.services.email_service import email_service
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

@tool
def human_assistance(query: str) -> str:
    """Request assistance from a human when the AI needs help with complex or sensitive queries."""
    return interrupt({"query": query})

@tool
def generate_literature_review(topic: str) -> str:
    """Generate a comprehensive literature review on any topic"""
    prompt = f"""
    Create a comprehensive literature review on {topic}.
    Include:
    1. Background and context
    2. Key theories and frameworks
    3. Recent findings and developments
    4. Current gaps and opportunities
    5. Methodological approaches
    6. Future directions and trends
    
    Structure this as a thorough review with proper citations and clear explanations.
    """
    llm = model_service.get_default_model()
    response = llm.invoke(prompt)
    return response.content

@tool
def generate_research_methodology(topic: str) -> str:
    """Suggest appropriate research methodologies for a given topic"""
    prompt = f"""
    Suggest comprehensive research methodologies for studying {topic}.
    Include:
    1. Quantitative approaches (surveys, experiments, statistical analysis)
    2. Qualitative approaches (interviews, case studies, content analysis)
    3. Mixed methods approaches
    4. Data collection strategies
    5. Sampling techniques
    6. Ethical considerations
    7. Validity and reliability measures
    
    Provide detailed explanations for each methodology and when to use them.
    """
    llm = model_service.get_default_model()
    response = llm.invoke(prompt)
    return response.content

@tool
def generate_study_plan(subject: str) -> str:
    """Create a comprehensive study plan for any subject"""
    prompt = f"""
    Create a detailed study plan for {subject}.
    Include:
    1. Learning objectives and outcomes
    2. Weekly study schedule
    3. Key topics and subtopics
    4. Study strategies and techniques
    5. Practice exercises and assessments
    6. Recommended resources and readings
    7. Progress tracking methods
    8. Time management tips
    
    Make this practical and actionable for effective learning.
    """
    llm = model_service.get_default_model()
    response = llm.invoke(prompt)
    return response.content

@tool
def generate_audio_response(text: str, voice: Optional[str] = None, lang_code: Optional[str] = None) -> str:
    """Generate audio from text using TTS (Text-to-Speech)"""
    if not tts_service.tts_available:
        return "TTS is not available. Please install kokoro and soundfile libraries."
    
    audio_files = tts_service.generate_audio(text, voice, lang_code)
    
    if audio_files:
        # Prefer returning a relative path that can be served
        try:
            rel_paths = []
            for p in audio_files:
                base = os.path.basename(p)
                rel_paths.append(f"audio_output/{base}")
            primary = rel_paths[0]
            return f"Audio generated successfully! File: {primary}"
        except Exception:
            return f"Audio generated successfully! Files saved: {', '.join(audio_files)}"
    else:
        return "No audio was generated from the text."

@tool
def browse_web_page(url: str) -> str:
    """Browses a web page or social media post and returns its content."""
    if not url or not url.startswith(('http://', 'https://')):
        return "Invalid URL. Please provide a full and valid URL starting with http:// or https://."

    try:
        # Detect platform and handle accordingly
        platform = _detect_platform(url)
        
        if platform == "instagram":
            return _browse_instagram_post(url)
        elif platform == "linkedin":
            return _browse_linkedin_post(url)
        elif platform == "twitter" or platform == "x":
            return _browse_twitter_post(url)
        else:
            return _browse_regular_webpage(url)
            
    except Exception as e:
        return f"An unexpected error occurred: {e}"

def _detect_platform(url: str) -> str:
    """Detect the platform from the URL"""
    url_lower = url.lower()
    
    if 'instagram.com' in url_lower:
        return "instagram"
    elif 'linkedin.com' in url_lower:
        return "linkedin"
    elif 'twitter.com' in url_lower or 'x.com' in url_lower:
        return "twitter"
    else:
        return "webpage"

def _browse_instagram_post(url: str) -> str:
    """Browse Instagram post content"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract Instagram post content
        content = []
        
        # Try to find post description
        description_selectors = [
            'meta[property="og:description"]',
            'meta[name="description"]',
            'div[data-testid="post-caption"]',
            'article div[dir="auto"]',
            '.caption',
            '[data-testid="post-caption"]'
        ]
        
        for selector in description_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get('content') or element.get_text(strip=True)
                if text and len(text) > 10:
                    content.append(f"📝 Post Description: {text}")
                    break
        
        # Try to find username
        username_selectors = [
            'meta[property="og:title"]',
            'a[href*="/p/"]',
            'header a',
            '.username'
        ]
        
        for selector in username_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get('content') or element.get_text(strip=True)
                if text and '@' in text:
                    content.append(f"👤 Username: {text}")
                    break
        
        # Try to find engagement metrics
        engagement_selectors = [
            '[data-testid="like-count"]',
            '[data-testid="comment-count"]',
            '.likes',
            '.comments'
        ]
        
        for selector in engagement_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                if text and any(word in text.lower() for word in ['like', 'comment', 'view']):
                    content.append(f"📊 Engagement: {text}")
                    break
        
        if content:
            result = f"📱 Instagram Post Analysis:\n\n"
            result += "\n".join(content)
            result += f"\n\n🔗 Source: {url}"
            return result
        else:
            return f"Could not extract Instagram post content. The post might be private or require authentication.\n\n🔗 URL: {url}"
            
    except Exception as e:
        return f"Error browsing Instagram post: {e}"

def _browse_linkedin_post(url: str) -> str:
    """Browse LinkedIn post content"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract LinkedIn post content
        content = []
        
        # Try to find post content
        content_selectors = [
            'meta[property="og:description"]',
            'meta[name="description"]',
            '.feed-shared-text',
            '.feed-shared-update-v2__description',
            '.share-text',
            '[data-testid="post-content"]'
        ]
        
        for selector in content_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get('content') or element.get_text(strip=True)
                if text and len(text) > 20:
                    content.append(f"📝 Post Content: {text}")
                    break
        
        # Try to find author name
        author_selectors = [
            'meta[property="og:title"]',
            '.feed-shared-actor__name',
            '.post-meta__headline',
            '.author-name'
        ]
        
        for selector in author_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get('content') or element.get_text(strip=True)
                if text and len(text) > 2:
                    content.append(f"👤 Author: {text}")
                    break
        
        # Try to find engagement metrics
        engagement_selectors = [
            '.social-details-social-counts',
            '.feed-shared-social-counts',
            '.reactions-count',
            '.comments-count'
        ]
        
        for selector in engagement_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                if text and any(word in text.lower() for word in ['like', 'comment', 'share', 'reaction']):
                    content.append(f"📊 Engagement: {text}")
                    break
        
        if content:
            result = f"💼 LinkedIn Post Analysis:\n\n"
            result += "\n".join(content)
            result += f"\n\n🔗 Source: {url}"
            return result
        else:
            return f"Could not extract LinkedIn post content. The post might be private or require authentication.\n\n🔗 URL: {url}"
            
    except Exception as e:
        return f"Error browsing LinkedIn post: {e}"

def _browse_twitter_post(url: str) -> str:
    """Browse Twitter/X post content"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract Twitter/X post content
        content = []
        
        # Try to find tweet content
        content_selectors = [
            'meta[property="og:description"]',
            'meta[name="description"]',
            '[data-testid="tweetText"]',
            '.tweet-text',
            '.js-tweet-text',
            'article div[lang]'
        ]
        
        for selector in content_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get('content') or element.get_text(strip=True)
                if text and len(text) > 10:
                    content.append(f"🐦 Tweet Content: {text}")
                    break
        
        # Try to find username
        username_selectors = [
            'meta[property="og:title"]',
            '[data-testid="User-Name"]',
            '.username',
            '.screen-name'
        ]
        
        for selector in username_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get('content') or element.get_text(strip=True)
                if text and '@' in text:
                    content.append(f"👤 Username: {text}")
                    break
        
        # Try to find engagement metrics
        engagement_selectors = [
            '[data-testid="like"]',
            '[data-testid="retweet"]',
            '[data-testid="reply"]',
            '.tweet-stats'
        ]
        
        engagement_metrics = []
        for selector in engagement_selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                if text and any(word in text.lower() for word in ['like', 'retweet', 'reply', 'view']):
                    engagement_metrics.append(text)
        
        if engagement_metrics:
            content.append(f"📊 Engagement: {', '.join(engagement_metrics)}")
        
        if content:
            result = f"🐦 Twitter/X Post Analysis:\n\n"
            result += "\n".join(content)
            result += f"\n\n🔗 Source: {url}"
            return result
        else:
            return f"Could not extract Twitter/X post content. The post might be private or require authentication.\n\n🔗 URL: {url}"
            
    except Exception as e:
        return f"Error browsing Twitter/X post: {e}"

def _browse_regular_webpage(url: str) -> str:
    """Browse regular web page content"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script_or_style in soup(['script', 'style']):
            script_or_style.decompose()
            
        # Get text and clean it up
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text[:5000]  # Return the first 5000 characters
    except requests.exceptions.RequestException as e:
        return f"Error fetching URL: {e}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"

@tool
def search_news(topic: str = "latest news", location: str = "global", 
               age_group: str = "general", max_results: int = 5, 
               time_period: str = "recent") -> str:
    """Search for news, headlines, and current events using Tavily search."""
    return news_service.search_news(topic, location, age_group, max_results, time_period)

@tool
def send_daily_news_email(recipient_email: str = "williamjohnie61@gmail.com", 
                         news_topics: Optional[List[str]] = None, 
                         custom_content: Optional[str] = None) -> str:
    """Send daily news digest email with flexible content from AI"""
    return email_service.send_daily_news_email(recipient_email, news_topics, custom_content)

@tool
def setup_daily_news_schedule(recipient_email: str = "williamjohnie61@gmail.com", 
                             time: str = "08:00", include_tanzania: bool = True, 
                             include_tech: bool = True) -> str:
    """Setup daily news email schedule (requires running the scheduler script separately)"""
    return email_service.setup_daily_news_schedule(recipient_email, time, include_tanzania, include_tech) 