import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
import gspread

# Define the scopes required for Drive and Sheets APIs
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), 'service_account.json')

def get_credentials():
    """Returns the authenticated Google Credentials object."""
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(f"Service account file not found: {SERVICE_ACCOUNT_FILE}")
    
    return service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )

def get_drive_service():
    """Returns an authenticated Google Drive API service client."""
    creds = get_credentials()
    return build('drive', 'v3', credentials=creds)

def get_sheets_client():
    """Returns an authenticated gspread client for Google Sheets."""
    creds = get_credentials()
    return gspread.authorize(creds)

def get_docs_service():
    """Returns an authenticated Google Docs API service client."""
    creds = get_credentials()
    return build('docs', 'v1', credentials=creds)
