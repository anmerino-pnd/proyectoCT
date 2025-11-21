from ct.settings.clients import (
    algolia_app_id,
    algolia_api_key,
    algolia_content_type
)
import cloudscraper 

scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'mobile': False
    }
)

scraper.headers.update({
    'X-Algolia-Application-Id': algolia_app_id,
    'X-Algolia-API-Key': algolia_api_key,
    'X-Algolia-UserToken': algolia_content_type
})

def algolia_query(query: str, user: str):
    
    pass