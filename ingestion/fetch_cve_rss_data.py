import os, requests, feedparser, json
import pandas as pd

def fetch_critical_cve_data(severity="CRITICAL", limit=50):
    """ Fetch critical CVE data from the NVD API. """
    url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cvssV3Severity={severity}&resultsPerPage={limit}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    response = requests.get(url, headers=headers)
    
    response.raise_for_status()
    data = response.json()
    
    cve_data = []
    
    for item in data.get("vulnerabilities", []):
        cve = item.get("cve", {})
        cve_data.append({
            "id": cve.get("id", ""),
            "summary": cve.get("descriptions", [{}])[0].get("value", ""),
            "published": cve.get("published", ""),
            "lastModified": cve.get("lastModified", ""),
            "cvss": cve.get("metrics", {}).get("cvssMetricV31", [{}])[0].get("cvssData", {}).get("baseScore", 5),
            "references": [ref.get("url") for ref in cve.get("references", [])]
        })
        
    return pd.DataFrame(cve_data)
    
def fetch_security_rss_feeds(feed_url="https://krebsonsecurity.com/feed/"):
    """ Fetch and parse security news from an RSS feed. """
    feed = feedparser.parse(feed_url)
    
    news_data = []
    
    for entry in feed.entries[:50]:
        news_data.append({
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "published": entry.get("published", ""),
            "summary": entry.get("summary", "")
        })
    
    return pd.DataFrame(news_data)

if __name__ == "__main__":
    cve_df = fetch_critical_cve_data(limit=10)
    print("Critical CVEs:")
    print(cve_df.head())
    
    news_df = fetch_security_rss_feeds()
    print("\nSecurity News:")
    print(news_df.head())