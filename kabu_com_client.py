import requests
import json
from datetime import datetime
from config import settings

class KabucomClient:
    def __init__(self):
        self.base_url = f"http://{settings.KABU_API_HOST}:{settings.KABU_API_PORT}/kabusapi"
        self.password = settings.KABU_API_PASSWORD
        self.token = None
        self.token_expiry = None
        self.host_header = f"localhost:{settings.KABU_API_PORT}"

    def _get_token(self):
        """
        Retrieves a valid API token. Refreshes if expired.
        """
        if self.token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.token

        url = f"{self.base_url}/token"
        headers = {
            "Content-Type": "application/json",
            "Host": self.host_header
        }
        payload = {"APIPassword": self.password}
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()
            self.token = data["Token"]
            # Simplified expiry handling (just assuming valid for a session for now)
            # In production, check 'ResultCode' and handle errors robustly
            return self.token
        except requests.exceptions.RequestException as e:
            print(f"Failed to get Token: {e}")
            raise

    def get_board(self, symbol: str, exchange: int = 1):
        """
        Fetches board data for a specific symbol.
        Exchange: 1=Tosho (Arrowhead), 3=Meisho, etc.
        """
        token = self._get_token()
        url = f"{self.base_url}/board/{symbol}@{exchange}"
        headers = {
            "X-API-KEY": token,
            "Host": self.host_header
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching board for {symbol}: {e}")
            return None

    def get_wallet_margin(self):
        """
        Fetches margin account balance (buying power).
        """
        token = self._get_token()
        url = f"{self.base_url}/wallet/margin" # Verify endpoint in official docs
        headers = {
            "X-API-KEY": token,
            "Host": self.host_header
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=5)
            return response.json()
        except Exception:
            return None
