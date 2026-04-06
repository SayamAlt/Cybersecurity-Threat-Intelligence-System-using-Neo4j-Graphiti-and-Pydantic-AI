from datetime import datetime, timezone
import json
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from core.risk_engine import compute_risk_score
from core.entity_extractor import extract_entities
import pandas as pd

import json

async def ingest_cve_data(graphiti_client: Graphiti, cve_data: pd.DataFrame):
    """ Ingests CVE data into the Graphiti knowledge graph. """
    print("Starting ingestion of CVEs...")
    for index, row in cve_data.iterrows():
        print(f"Ingesting CVE {index + 1}/{len(cve_data)}: {row['id']}")
        try:
            entities = await extract_entities(row["summary"])
        except Exception as e:
            print(f"Failed to extract entities for {row['id']}: {e}")
            entities = {}
        risk_score = compute_risk_score(row["cvss"])
        
        json_data = json.dumps({
            "cve": row['id'],
            "description": row['summary'],
            "cvss": row['cvss'],
            "risk_level": risk_score,
            "entities": entities
        })
        
        await graphiti_client.add_episode(
            name=row["id"],
            episode_body=json_data,
            source=EpisodeType.json,
            source_description="NVD API Critical CVEs Data",
            reference_time=datetime.now(timezone.utc),
            group_id=f"CVE-{row['id']}"
        )
        
async def ingest_rss_feed(graphiti_client: Graphiti, news_data: pd.DataFrame):
    """ Ingests news data from an RSS feed into the Graphiti knowledge graph. """
    print("Starting ingestion of RSS Feeds...")
    for index, row in news_data.iterrows():
        print(f"Ingesting RSS {index + 1}/{len(news_data)}: {row['title']}")
        
        json_data = json.dumps({
            "title": row['title'],
            "link": row['link'],
            "published": row['published'],
            "summary": row['summary']
        })
        
        await graphiti_client.add_episode(
            name=row["title"],
            episode_body=json_data,
            source=EpisodeType.json,
            source_description="RSS Cybersecurity News Feed Data",
            reference_time=datetime.now(timezone.utc),
            group_id=f"RSS-{index}"
        )