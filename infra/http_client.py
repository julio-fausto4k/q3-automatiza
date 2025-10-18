# infra/http_client.py
"""HTTP client with retry logic and rate limiting."""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from utils.validators import _env_int, _env_float, _flag
import os

class HTTPClient:
    def __init__(self):
        self.session = requests.Session()
        self._configure_retries()
    
    def _configure_retries(self):
        """Configure HTTP retry strategy."""
        retry_total = _env_int("Q3_HTTP_RETRY_TOTAL", 1)
        backoff_factor = _env_float("Q3_HTTP_BACKOFF", 0.1)
        respect_retry_after = _flag("Q3_HTTP_RESPECT_RETRY_AFTER", False)
        
        retry_strategy = Retry(
            total=retry_total,
            backoff_factor=backoff_factor,
            respect_retry_after_header=respect_retry_after,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def request(self, method: str, url: str, **kwargs):
        """Make HTTP request with configured retry strategy."""
        return self.session.request(method, url, **kwargs)
    
    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)
    
    def post(self, url: str, **kwargs):
        return self.request("POST", url, **kwargs)
    
    def put(self, url: str, **kwargs):
        return self.request("PUT", url, **kwargs)
    
    def delete(self, url: str, **kwargs):
        return self.request("DELETE", url, **kwargs)

# Global HTTP client instance
http_client = HTTPClient()