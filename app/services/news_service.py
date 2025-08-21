import re
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
from langchain_tavily import TavilySearch

from app.config import settings
from app.services.model_service import model_service
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

class NewsService:
    """Service for handling news-related operations"""
    
    def __init__(self):
        self.tavily_search = TavilySearch(max_results=10)
        self.llm = model_service.get_default_model()
    
    def search_news(self, topic: str = "latest news", location: str = "global", 
                   age_group: str = "general", max_results: int = 5, 
                   time_period: str = "recent") -> str:
        """Search for news using Tavily search"""
        try:
            # Create optimized search query based on parameters
            search_query = self._build_news_search_query(topic, location, age_group, time_period)
            
            # Use Tavily search to get news
            search_results = self.tavily_search.invoke(search_query)
            
            if not search_results or not hasattr(search_results, 'content'):
                return f"No news found for '{topic}' in {location}."
            
            # Extract URLs and headlines from search results
            news_items = self._extract_news_from_search_results(search_results.content, max_results)
            
            if not news_items:
                return f"No relevant news found for '{topic}' in {location}."
            
            # Fetch and summarize each article
            summarized_news = self._fetch_and_summarize_articles(news_items, topic, location, age_group)
            
            return summarized_news
            
        except Exception as e:
            logger.error(f"Error in search_news: {e}")
            return f"Error searching for news: {e}"
    
    def _build_news_search_query(self, topic: str, location: str, age_group: str, time_period: str) -> str:
        """Build an optimized search query for news based on parameters"""
        
        # Base query
        query_parts = [topic]
        
        # Add location context
        if location.lower() != "global":
            query_parts.append(f"in {location}")
        
        # Add time period context
        time_contexts = {
            "recent": "latest breaking news",
            "today": "today's news",
            "week": "this week's news",
            "month": "this month's news"
        }
        if time_period in time_contexts:
            query_parts.append(time_contexts[time_period])
        
        # Add age-appropriate context
        age_contexts = {
            "youth": "trending viral news",
            "senior": "important developments",
            "professional": "business and industry news",
            "general": "mainstream news"
        }
        if age_group in age_contexts:
            query_parts.append(age_contexts[age_group])
        
        # Add news-specific terms
        query_parts.extend(["news", "headlines", "latest updates"])
        
        return " ".join(query_parts)
    
    def _extract_news_from_search_results(self, search_content: str, max_results: int) -> List[Dict]:
        """Extract news URLs and headlines from Tavily search results"""
        try:
            news_items = []
            lines = search_content.split('\n')
            
            for line in lines:
                line = line.strip()
                if line and len(line) > 20:
                    # Look for lines that might contain URLs
                    if 'http' in line and any(domain in line.lower() for domain in [
                        'news', 'bbc', 'cnn', 'reuters', 'ap', 'guardian', 'nytimes', 
                        'washingtonpost', 'techcrunch', 'theverge', 'arstechnica', 
                        'wired', 'mit', 'citizen', 'dailynews', 'ippmedia', 'mwananchi'
                    ]):
                        # Extract URL and title
                        url_match = re.search(r'https?://[^\s]+', line)
                        if url_match:
                            url = url_match.group(0)
                            # Clean up the title (remove URL and extra formatting)
                            title = line.replace(url, '').replace('•', '').replace('-', '').strip()
                            if title and len(title) > 10:
                                news_items.append({
                                    'url': url,
                                    'title': title,
                                    'source': self._extract_source_from_url(url)
                                })
            
            return news_items[:max_results]
            
        except Exception as e:
            logger.error(f"Error extracting news from search results: {e}")
            return []
    
    def _extract_source_from_url(self, url: str) -> str:
        """Extract source name from URL"""
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            # Remove www. and common TLDs
            source = domain.replace('www.', '').split('.')[0]
            return source.title()
        except:
            return "Unknown Source"
    
    def _fetch_and_summarize_articles(self, news_items: List[Dict], topic: str, 
                                    location: str, age_group: str) -> str:
        """Fetch full articles and generate summaries"""
        try:
            summarized_articles = []
            
            for i, item in enumerate(news_items, 1):
                try:
                    logger.info(f"Fetching article {i}/{len(news_items)}: {item['title'][:50]}...")
                    
                    # Fetch the full article content
                    article_content = self._browse_web_page(item['url'])
                    
                    if article_content and not article_content.startswith("Error") and len(article_content) > 100:
                        # Generate summary using LLM
                        summary = self._generate_article_summary(article_content, item['title'], age_group)
                        
                        summarized_articles.append({
                            'title': item['title'],
                            'summary': summary,
                            'url': item['url'],
                            'source': item['source']
                        })
                    else:
                        # If we can't fetch the article, just include the headline
                        summarized_articles.append({
                            'title': item['title'],
                            'summary': "Article content could not be fetched. Please visit the source for full details.",
                            'url': item['url'],
                            'source': item['source']
                        })
                    
                except Exception as e:
                    logger.error(f"Error processing article {i}: {e}")
                    continue
            
            # Format the results
            return self._format_summarized_news(summarized_articles, topic, location, age_group)
            
        except Exception as e:
            logger.error(f"Error fetching and summarizing articles: {e}")
            return f"Error processing news articles: {e}"
    
    def _browse_web_page(self, url: str) -> str:
        """Browse web page content"""
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
    
    def _generate_article_summary(self, article_content: str, title: str, age_group: str) -> str:
        """Generate a concise summary of the article content"""
        try:
            # Truncate content if too long to avoid token limits
            max_content_length = 3000
            if len(article_content) > max_content_length:
                article_content = article_content[:max_content_length] + "..."
            
            # Create age-appropriate summary prompt
            age_context = {
                "youth": "Write a concise, engaging summary suitable for young adults",
                "senior": "Write a clear, detailed summary with important context",
                "professional": "Write a professional summary focusing on key facts and implications",
                "general": "Write a clear, balanced summary for general audience"
            }
            
            prompt = f"""
            {age_context.get(age_group, age_context['general'])} for this news article:
            
            Title: {title}
            
            Article Content:
            {article_content}
            
            Provide a 2-3 sentence summary that captures the main points and key details.
            Focus on the most important information and maintain accuracy.
            """
            
            response = self.llm.invoke(prompt)
            return response.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return "Summary could not be generated."
    
    def _format_summarized_news(self, summarized_articles: List[Dict], topic: str, 
                               location: str, age_group: str) -> str:
        """Format the summarized news articles with proper structure"""
        try:
            location_emoji = self._get_location_emoji(location)
            topic_emoji = self._get_topic_emoji(topic)
            
            result = f"{location_emoji} {topic_emoji} News Summary for {location.title()}:\n\n"
            
            for i, article in enumerate(summarized_articles, 1):
                result += f"📰 **{i}. {article['title']}**\n"
                result += f"📝 {article['summary']}\n"
                result += f"🔗 Source: [{article['source']}]({article['url']})\n"
                result += f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                result += "─" * 50 + "\n\n"
            
            result += f"🎯 Optimized for: {age_group.title()} audience\n"
            result += f"📊 Total articles: {len(summarized_articles)}"
            
            return result
            
        except Exception as e:
            logger.error(f"Error formatting summarized news: {e}")
            return f"Error formatting news results: {e}"
    
    def _get_location_emoji(self, location: str) -> str:
        """Get appropriate emoji for location"""
        location_lower = location.lower()
        if 'tanzania' in location_lower or 'dar' in location_lower:
            return "🇹🇿"
        elif 'kenya' in location_lower:
            return "🇰🇪"
        elif 'uganda' in location_lower:
            return "🇺🇬"
        elif 'africa' in location_lower:
            return "🌍"
        elif 'usa' in location_lower or 'america' in location_lower:
            return "🇺🇸"
        elif 'uk' in location_lower or 'britain' in location_lower:
            return "🇬🇧"
        elif 'europe' in location_lower:
            return "🇪🇺"
        elif 'asia' in location_lower:
            return "🌏"
        else:
            return "🌍"
    
    def _get_topic_emoji(self, topic: str) -> str:
        """Get appropriate emoji for topic"""
        topic_lower = topic.lower()
        if any(word in topic_lower for word in ['tech', 'technology', 'ai', 'artificial intelligence']):
            return "💻"
        elif any(word in topic_lower for word in ['business', 'economy', 'finance']):
            return "💰"
        elif any(word in topic_lower for word in ['sports', 'football', 'basketball']):
            return "⚽"
        elif any(word in topic_lower for word in ['politics', 'government']):
            return "🏛️"
        elif any(word in topic_lower for word in ['health', 'medical', 'covid']):
            return "🏥"
        elif any(word in topic_lower for word in ['entertainment', 'movie', 'music']):
            return "🎬"
        elif any(word in topic_lower for word in ['science', 'research']):
            return "🔬"
        else:
            return "📰"

# Global news service instance
news_service = NewsService() 