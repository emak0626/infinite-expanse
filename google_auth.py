import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from googleapiclient.discovery import build
import gspread
import pickle

# Define the scopes required for Drive and Sheets APIs
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents.readonly',
    'https://www.googleapis.com/auth/docs'
]

SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), 'service_account.json')
TOKEN_FILE = os.path.join(os.path.dirname(__file__), 'token.json')

def get_credentials():
    """Returns the authenticated Google Credentials object. 
    Prioritizes user token.json (OAuth2) over service account.
    """
    creds = None
    # 1. Try OAuth2 User Token (for emori@m-e-asset.com)
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    # If no valid user token, handle refresh or use service account
    if creds and creds.valid:
        return creds
    elif creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
        return creds
    
    # 2. Fallback to Service Account
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        print("Using Service Account for Google API access.")
        return service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
    
    raise FileNotFoundError("Neither token.json nor service_account.json was found.")

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
