"""Google News RSS scraper for company news articles.

Scrapes Google News RSS feed for recent news about companies.
Used as input for sentiment analysis pipeline.

Adapted from Dexter's search/google.py and search/utils.py.
"""

import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from xml.etree import ElementTree as ET

import requests

logger = logging.getLogger(__name__)


@dataclass
class NewsArticle:
    """Represents a news article from Google News."""

    title: str
    url: str
    published_date: Optional[datetime] = None
    source: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "title": self.title,
            "url": self.url,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "source": self.source,
        }


class NewsScraper:
    """Scrapes Google News RSS for company news.

    Usage:
        scraper = NewsScraper()
        articles = scraper.search_ticker("AAPL", company_name="Apple", max_results=10)

        for article in articles:
            print(f"{article.title} - {article.url}")
    """

    GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"
    DEFAULT_TIMEOUT = 10

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        resolve_urls: bool = True,
        max_workers: int = 5,
    ):
        """Initialize the news scraper.

        Args:
            timeout: HTTP request timeout in seconds
            resolve_urls: If True, resolve Google News redirect URLs to actual article URLs
            max_workers: Max parallel workers for URL resolution
        """
        self.timeout = timeout
        self.resolve_urls = resolve_urls
        self.max_workers = max_workers
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; ZuseBot/1.0)"
        })

    def search(self, query: str, max_results: int = 10) -> List[NewsArticle]:
        """Search Google News for articles matching a query.

        Args:
            query: Search query string
            max_results: Maximum number of results to return

        Returns:
            List of NewsArticle objects
        """
        # Build RSS URL
        encoded_query = query.replace(" ", "%20")
        url = f"{self.GOOGLE_NEWS_RSS_URL}?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

        try:
            response = self._session.get(url, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch Google News RSS: {e}")
            return []

        # Parse RSS
        articles = self._parse_rss(response.text, max_results)

        # Optionally resolve URLs
        if self.resolve_urls and articles:
            articles = self._resolve_urls_parallel(articles)

        return articles

    def search_ticker(
        self,
        ticker: str,
        company_name: Optional[str] = None,
        max_results: int = 10,
    ) -> List[NewsArticle]:
        """Search news for a specific stock ticker.

        Builds a query combining ticker and optional company name for better results.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")
            company_name: Optional company name (e.g., "Apple Inc")
            max_results: Maximum number of results to return

        Returns:
            List of NewsArticle objects
        """
        # Build query - ticker + optional company name
        if company_name:
            # Use company name + stock for better results
            query = f"{company_name} stock"
        else:
            query = f"{ticker} stock"

        return self.search(query, max_results)

    def search_multiple_tickers(
        self,
        tickers: List[str],
        company_names: Optional[dict[str, str]] = None,
        max_per_ticker: int = 5,
    ) -> dict[str, List[NewsArticle]]:
        """Search news for multiple tickers.

        Args:
            tickers: List of ticker symbols
            company_names: Optional mapping of ticker -> company name
            max_per_ticker: Maximum results per ticker

        Returns:
            Dictionary mapping ticker -> list of articles
        """
        company_names = company_names or {}
        results: dict[str, List[NewsArticle]] = {}

        for ticker in tickers:
            company_name = company_names.get(ticker)
            articles = self.search_ticker(ticker, company_name, max_per_ticker)
            results[ticker] = articles

        return results

    def _parse_rss(self, xml_content: str, max_results: int) -> List[NewsArticle]:
        """Parse RSS XML into NewsArticle objects.

        Args:
            xml_content: RSS XML string
            max_results: Maximum number of results to parse

        Returns:
            List of NewsArticle objects
        """
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            logger.warning(f"Failed to parse RSS XML: {e}")
            return []

        articles: List[NewsArticle] = []

        # Find all items (fetch extra in case some fail)
        items = root.findall(".//item")[: max_results * 2]

        for item in items:
            title_elem = item.find("title")
            link_elem = item.find("link")
            date_elem = item.find("pubDate")
            source_elem = item.find("source")

            title = title_elem.text if title_elem is not None else "No title"
            url = link_elem.text if link_elem is not None else ""
            pub_date_str = date_elem.text if date_elem is not None else ""
            source = source_elem.text if source_elem is not None else None

            # Skip if no URL
            if not url:
                continue

            articles.append(
                NewsArticle(
                    title=self._clean_text(title),
                    url=url,
                    published_date=self._parse_rss_date(pub_date_str),
                    source=source,
                )
            )

            if len(articles) >= max_results:
                break

        return articles

    def _resolve_urls_parallel(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Resolve Google News redirect URLs in parallel.

        Args:
            articles: List of articles with Google News URLs

        Returns:
            List of articles with resolved URLs
        """
        resolved_articles: List[NewsArticle] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all URL resolution tasks
            future_to_article = {
                executor.submit(self._resolve_google_news_url, article.url): article
                for article in articles
            }

            # Collect results
            for future in as_completed(future_to_article):
                article = future_to_article[future]
                try:
                    resolved_url = future.result()
                    resolved_articles.append(
                        NewsArticle(
                            title=article.title,
                            url=resolved_url,
                            published_date=article.published_date,
                            source=article.source,
                        )
                    )
                except Exception as e:
                    logger.debug(f"Failed to resolve URL {article.url}: {e}")
                    # Keep original URL on failure
                    resolved_articles.append(article)

        return resolved_articles

    def _resolve_google_news_url(self, url: str) -> str:
        """Resolve a Google News redirect URL to the actual article URL.

        Args:
            url: Google News URL to resolve

        Returns:
            Resolved article URL, or original URL if resolution fails
        """
        if not url or "news.google.com" not in url:
            return url

        try:
            from googlenewsdecoder import gnewsdecoder

            result = gnewsdecoder(url, interval=1)
            if result.get("status"):
                return result["decoded_url"]
            return url
        except ImportError:
            logger.warning(
                "googlenewsdecoder not installed. Install with: pip install googlenewsdecoder"
            )
            return url
        except Exception as e:
            logger.debug(f"Failed to decode Google News URL: {e}")
            return url

    def _parse_rss_date(self, date_str: str) -> Optional[datetime]:
        """Parse RSS pubDate string to datetime.

        Args:
            date_str: RSS date string (e.g., "Sat, 30 Nov 2024 12:00:00 GMT")

        Returns:
            Parsed datetime or None if parsing fails
        """
        if not date_str:
            return None

        try:
            # Remove timezone suffix
            date_str = date_str.replace(" GMT", "").replace(" +0000", "")
            return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S")
        except ValueError:
            pass

        # Try alternative date patterns
        return self._parse_date_fallback(date_str)

    def _parse_date_fallback(self, date_str: str) -> Optional[datetime]:
        """Fallback date parsing for non-standard formats.

        Args:
            date_str: Date string to parse

        Returns:
            Parsed datetime or None
        """
        patterns = [
            (r"(\d{4}-\d{2}-\d{2})", "%Y-%m-%d"),
            (r"(\d{1,2}/\d{1,2}/\d{4})", "%m/%d/%Y"),
            (r"(\w+ \d{1,2}, \d{4})", "%B %d, %Y"),
        ]

        for pattern, fmt in patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    return datetime.strptime(match.group(1), fmt)
                except ValueError:
                    continue

        return None

    def _clean_text(self, text: str) -> str:
        """Clean text by removing HTML and normalizing characters.

        Args:
            text: Text to clean

        Returns:
            Cleaned text
        """
        if not text:
            return text

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)

        # Unescape HTML entities
        text = html.unescape(text)

        # Replace common unicode characters
        unicode_replacements = {
            "\u2018": "'",
            "\u2019": "'",
            "\u201c": '"',
            "\u201d": '"',
            "\u2013": "-",
            "\u2014": "-",
            "\u2026": "...",
            "\u00a0": " ",
            "\u00ae": "(R)",
            "\u2122": "(TM)",
        }
        for unicode_char, replacement in unicode_replacements.items():
            text = text.replace(unicode_char, replacement)

        # Convert to ASCII (remove remaining non-ASCII)
        text = text.encode("ascii", "ignore").decode("ascii")

        # Normalize whitespace
        text = " ".join(text.split())

        return text

    def close(self):
        """Close the HTTP session."""
        self._session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
