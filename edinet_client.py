import aiohttp
import asyncio
import io
import zipfile
import re
from datetime import datetime, date
import logging
from config import settings

logger = logging.getLogger(__name__)

class EdinetClient:
    """
    Client for Financial Services Agency's EDINET API (Public).
    Documentation: https://disclosure2.edinet-fsa.go.jp/EKW0EZ0001.html
    """
    BASE_URL = "https://api.edinet-fsa.go.jp/api/v2"

    def __init__(self):
        self.api_key = settings.EDINET_API_KEY # Optional for some endpoints, but good to have
        
    async def get_documents_on_date(self, target_date: date = None):
        """
        Fetches the list of submitted documents for a specific date.
        """
        if target_date is None:
            target_date = date.today()
        
        url = f"{self.BASE_URL}/documents.json"
        params = {
            "date": target_date.strftime("%Y-%m-%d"),
            "type": 2 # 2 means metadata of documents
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        if self.api_key:
            params["Subscription-Key"] = self.api_key
        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("results", [])
                    else:
                        err_text = await resp.text()
                        logger.error(f"EDINET API failed with status {resp.status}. Response: {err_text}")
                        return []
            except Exception as e:
                logger.error(f"EDINET connection error: {e}")
                return []

    async def filter_relevant_documents(self, documents: list, target_symbols: list[str]):
        """
        Filters documents for specific symbols and document types (e.g., Annual reports, Quarterlies).
        Note: EDINET uses its own entity codes (EDINET Code), but also includes SEC codes (Security Codes/Ticker).
        """
        filtered = []
        for doc in documents:
            # securityCode in EDINET is 5-digit (e.g., 72030 for Toyota)
            sec_code = doc.get("secCode")
            if sec_code:
                symbol = sec_code[:4] # Convert to 4-digit stock symbol
                if symbol in target_symbols:
                    # Filter for major reports (Annual, Semi-annual, Quarter, Extraordinary)
                    # docTypeCode: 120 (Annual), 130 (Quarterly), 140 (Semi-annual)
                    if doc.get("docTypeCode") in ["120", "130", "140", "150", "160"]:
                        filtered.append({
                            "symbol": symbol,
                            "docID": doc.get("docID"),
                            "title": doc.get("docDescription"),
                            "date": doc.get("submitDateTime"),
                            "pdf_url": f"{self.BASE_URL}/documents/{doc.get('docID')}?type=2",
                            "zip_url": f"{self.BASE_URL}/documents/{doc.get('docID')}?type=1"
                        })
        return filtered

    async def get_document_text(self, doc_id: str) -> str:
        """
        Downloads the ZIP file for a document, extracts the main HTML content,
        and converts it to a clean text snippet for LLM analysis.
        """
        url = f"{self.BASE_URL}/documents/{doc_id}"
        params = {"type": 1} # ZIP (XBRL/HTML)
        if self.api_key:
            params["Subscription-Key"] = self.api_key

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to download EDINET doc {doc_id}: {resp.status}")
                        return ""
                    
                    zip_data = await resp.read()
                    
                    with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
                        # EDINET ZIPs contain PublicDoc folder with HTML versions of the disclosure
                        # We look for the main content HTML file.
                        html_files = [f for f in z.namelist() if f.startswith("PublicDoc/") and f.endswith(".htm")]
                        
                        if not html_files:
                            return "【開示内容の抽出失敗】HTMLファイルが見つかりませんでした。"
                        
                        # Use the first one (usually the main one) or combine if few
                        all_text = ""
                        for html_file in html_files[:3]: # Limit to first 3 files to avoid too much data
                            with z.open(html_file) as f:
                                try:
                                    html_content = f.read().decode("utf-8")
                                except UnicodeDecodeError:
                                    # Try other encodings if needed (e.g., cp932 for Japanese docs)
                                    try:
                                        html_content = f.read().decode("cp932")
                                    except:
                                        continue
                                
                                # Basic regex-based text extraction (dependency-free)
                                # 1. Remove script/style tags
                                html_content = re.sub(r'<(script|style).*?>.*?</\1>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
                                # 2. Replace tags with newlines/spaces
                                text = re.sub(r'<.*?>', '\n', html_content)
                                # 3. Clean up whitespace
                                text = re.sub(r'\n+', '\n', text).strip()
                                all_text += text + "\n---\n"
                        
                        # Return a truncated version if it's too long
                        max_chars = 3000
                        if len(all_text) > max_chars:
                            all_text = all_text[:max_chars] + "\n...(以下略)"
                        
                        return all_text
                        
            except Exception as e:
                logger.error(f"Error fetching EDINET document content: {e}")
                return f"【エラー】データ取得中に例外が発生しました: {str(e)}"

async def main_test():
    client = EdinetClient()
    # Test for yesterday or a known date if today is empty
    docs = await client.get_documents_on_date(date(2024, 6, 20)) # Example date
    print(f"Total documents: {len(docs)}")
    relevant = await client.filter_relevant_documents(docs, ["7203", "9984", "8001"])
    for r in relevant:
        print(f"Found: {r['symbol']} - {r['title']} ({r['pdf_url']})")

if __name__ == "__main__":
    asyncio.run(main_test())
