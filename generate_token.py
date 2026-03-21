import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow

# SCOPES from google_auth.py
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents.readonly',
    'https://www.googleapis.com/auth/docs'
]

CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'

# Allow HTTP for local authentication (required for Docker/localhost)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

def main():
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"ERROR: {CREDENTIALS_FILE} が見つかりません。")
        return

    # Use 'http://localhost' as redirect_uri for manual copy-paste from address bar
    flow = InstalledAppFlow.from_client_secrets_file(
        CREDENTIALS_FILE, 
        SCOPES,
        redirect_uri='http://localhost'
    )
    
    auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
    
    print("\n" + "="*50)
    print("1. 以下のURLをブラウザ（Windows側）で開いてください:")
    print(f"\n{auth_url}\n")
    print("2. 認証を完了すると、ブラウザが 'localhost' にリダイレクトされます。")
    print("3. ブラウザには「アクセスできません」と出ますが、**アドレスバーのURL**をすべてコピーしてください。")
    print("   例: http://localhost/?code=4/0Af...&scope=...")
    print("="*50 + "\n")
    
    full_url = input("コピーしたURL全体をここに貼り付けてください: ").strip()
    
    try:
        # Extract code from URL manually or let fetch_token handle it if it's the full URL
        # fetch_token handles the full URL if it looks like one.
        flow.fetch_token(authorization_response=full_url)
        creds = flow.credentials

        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
            
        print(f"\nSUCCESS: {TOKEN_FILE} が正常に作成されました。")
    except Exception as e:
        print(f"\nERROR: 認証に失敗しました。 {e}")

if __name__ == "__main__":
    main()
