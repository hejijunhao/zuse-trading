"""Miner services - Individual data source integrations.

Services layer contains files that execute single-responsibility tasks:
- http_client: Base HTTP client with retries/rate-limiting
- universe_seeder: Seeds instrument table from Wikipedia + Yahoo Finance
- constants: SEC filing item mappings
- ohlcv_fetcher: Fetches OHLCV price bars
- fundamentals_fetcher: Fetches income/balance/cashflow statements
- estimates_fetcher: Fetches analyst consensus estimates
- filings_fetcher: Fetches SEC 10-K/10-Q/8-K filings
- news_scraper: Scrapes Google News RSS for company news
"""

from .universe_seeder import (
    ConstituentFetcher,
    YahooFinanceEnricher,
    InstrumentMapper,
    UniverseSeeder,
)
from .http_client import (
    HTTPClient,
    HTTPClientError,
    RateLimitError,
    APIError,
    FinancialDatasetsHTTPClient,
)
from .constants import (
    ITEMS_10K_MAP,
    ITEMS_10K,
    ITEMS_10K_KEY_SECTIONS,
    ITEMS_10Q_MAP,
    ITEMS_10Q,
    ITEMS_10Q_KEY_SECTIONS,
    ITEMS_8K_MAP,
    ITEMS_8K,
    ITEMS_8K_KEY_SECTIONS,
    format_items_description,
    get_item_description,
)
from .ohlcv_fetcher import (
    OHLCVFetcher,
    PriceBar,
    PriceSnapshot,
)
from .fundamentals_fetcher import (
    FundamentalsFetcher,
    FinancialStatementData,
)
from .estimates_fetcher import (
    EstimatesFetcher,
    EstimateData,
)
from .filings_fetcher import (
    FilingsFetcher,
    FilingMetadata,
    FilingSection,
    FilingContent,
)
from .news_scraper import (
    NewsScraper,
    NewsArticle,
)

__all__ = [
    # Universe seeder
    "ConstituentFetcher",
    "YahooFinanceEnricher",
    "InstrumentMapper",
    "UniverseSeeder",
    # HTTP client
    "HTTPClient",
    "HTTPClientError",
    "RateLimitError",
    "APIError",
    "FinancialDatasetsHTTPClient",
    # SEC filing constants
    "ITEMS_10K_MAP",
    "ITEMS_10K",
    "ITEMS_10K_KEY_SECTIONS",
    "ITEMS_10Q_MAP",
    "ITEMS_10Q",
    "ITEMS_10Q_KEY_SECTIONS",
    "ITEMS_8K_MAP",
    "ITEMS_8K",
    "ITEMS_8K_KEY_SECTIONS",
    "format_items_description",
    "get_item_description",
    # OHLCV fetcher
    "OHLCVFetcher",
    "PriceBar",
    "PriceSnapshot",
    # Fundamentals fetcher
    "FundamentalsFetcher",
    "FinancialStatementData",
    # Estimates fetcher
    "EstimatesFetcher",
    "EstimateData",
    # Filings fetcher
    "FilingsFetcher",
    "FilingMetadata",
    "FilingSection",
    "FilingContent",
    # News scraper
    "NewsScraper",
    "NewsArticle",
]
