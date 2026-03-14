
import asyncio
from database import AsyncSessionLocal
from sqlalchemy import text
from drive_manager import DriveManager
from google_auth import get_drive_service

async def audit():
    print("--- Database Audit ---")
    async with AsyncSessionLocal() as s:
        # Check analysis
        r = await s.execute(text('SELECT count(*) FROM ai_analysis'))
        print(f"Total AI Reports: {r.scalar()}")
        
        r = await s.execute(text('SELECT symbol, score, thinking_level FROM ai_analysis ORDER BY created_at DESC LIMIT 5'))
        for row in r:
            print(f"  - {row.symbol}: Score={row.score} ({row.thinking_level})")

    print("\n--- Google Drive Audit ---")
    dm = DriveManager()
    root_id = dm.get_folder_id(dm.root_folder_name)
    print(f"Root Folder Name: {dm.root_folder_name}")
    print(f"Root Folder ID: {root_id}")
    
    if root_id:
        s = get_drive_service()
        q = f"'{root_id}' in parents and trashed = false"
        results = s.files().list(q=q, fields='files(id, name, webViewLink)').execute()
        files = results.get('files', [])
        print(f"Files in Root:")
        for f in files:
            print(f"  - {f['name']} (ID: {f['id']})")
            # If it's 01_Market_Data, check inside
            if f['name'] == '01_Market_Data':
                q2 = f"'{f['id']}' in parents and trashed = false"
                res2 = s.files().list(q=q2, fields='files(id, name, webViewLink)').execute()
                for f2 in res2.get('files', []):
                    print(f"    - {f2['name']} (ID: {f2['id']})")

if __name__ == "__main__":
    asyncio.run(audit())
