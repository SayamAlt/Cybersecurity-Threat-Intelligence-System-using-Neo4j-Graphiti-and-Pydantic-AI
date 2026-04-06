import requests
import time
import os
from typing import Optional, Dict

class AuraManager:
    """
    Manages Neo4j Aura instances via the Aura API.
    Used for automatically resuming paused instances.
    """
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://api.neo4j.io/v1"
        self.access_token: Optional[str] = None
        self.token_expiry: float = 0

    def _get_token(self) -> str:
        """Authenticates and retrieves an OAuth2 access token."""
        if self.access_token and time.time() < self.token_expiry:
            return self.access_token
        
        # The token endpoint is at the root and NOT under /v1
        auth_url = "https://api.neo4j.io/oauth/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        response = requests.post(
            auth_url,
            auth=(self.client_id, self.client_secret),
            data={"grant_type": "client_credentials"},
            headers=headers
        )
        
        if response.status_code != 200:
            # Include more detailed error feedback from the API response
            raise Exception(f"OAuth Token Error ({response.status_code}): {response.text}")
        
        
        data = response.json()
        self.access_token = data["access_token"]
        # Set expiry slightly earlier than reported (default is 1h)
        self.token_expiry = time.time() + data.get("expires_in", 3600) - 60
        return self.access_token

    def get_instance_status(self, instance_id: str) -> str:
        """Retrieves the current status of the instance."""
        token = self._get_token()
        url = f"{self.base_url}/instances/{instance_id}"
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()["data"]["status"]

    def resume_instance(self, instance_id: str) -> bool:
        """Triggers a resume operation if the instance is paused."""
        status = self.get_instance_status(instance_id)
        
        if status == "running":
            return True
        
        if status != "paused":
            # If it's already resuming, we just need to wait
            return False

        token = self._get_token()
        url = f"{self.base_url}/instances/{instance_id}/resume"
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.post(url, headers=headers)
        # 202 Accepted means the resume request was successful
        return response.status_code == 202

    def wait_for_running(self, instance_id: str, timeout_minutes: int = 10, callback=None) -> bool:
        """Polls the instance status until it becomes 'running'."""
        start_time = time.time()
        
        while time.time() - start_time < (timeout_minutes * 60):
            status = self.get_instance_status(instance_id)
            if status == "running":
                return True
            
            if callback:
                callback(status)
            
            time.sleep(15) # Poll every 15 seconds
            
        return False

def ensure_aura_instance_running(
    client_id: str, 
    client_secret: str, 
    instance_id: str, 
    status_callback=None
) -> bool:
    """
    High-level utility to ensure an Aura instance is started.
    Returns True if the instance is running or successfully started.
    """
    if not all([client_id, client_secret, instance_id]):
        # If any credentials are missing, we can't manage via API
        return False
        
    manager = AuraManager(client_id, client_secret)
    
    try:
        # Check and trigger resume if needed
        manager.resume_instance(instance_id)
        
        # Wait for 'running' status
        return manager.wait_for_running(instance_id, callback=status_callback)
    except Exception as e:
        if status_callback:
            status_callback(f"error: {str(e)}")
        return False
