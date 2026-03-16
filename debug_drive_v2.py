import os
import json
import logging
from google_auth import get_drive_service
from googleapiclient.errors import HttpError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def debug_drive():
    logger.info("--- Google Drive Debug Start ---")
    
    # Check service account file
    sa_path = "service_account.json"
    if not os.path.exists(sa_path):
        logger.error(f"FATAL: {sa_path} not found in {os.getcwd()}")
        return
    
    try:
        with open(sa_path, 'r') as f:
            sa_data = json.load(f)
            logger.info(f"Service Account Email: {sa_data.get('client_email')}")
    except Exception as e:
        logger.error(f"Failed to read service account file: {e}")
        return

    try:
        logger.info("Initializing Drive Service...")
        service = get_drive_service()
        logger.info("Service initialized successfully.")
        
        # Try simple list
        logger.info("Testing API connectivity (listing files)...")
        results = service.files().list(pageSize=10, fields="nextPageToken, files(id, name)").execute()
        items = results.get('files', [])
        logger.info(f"Found {len(items)} files in Service Account Drive.")
        for item in items:
            logger.info(f" - {item['name']} ({item['id']})")

        # Try searching for system root
        from drive_manager import DriveManager
        dm = DriveManager()
        logger.info(f"System Root Name: {dm.root_folder_name}")
        root_id = dm.get_folder_id(dm.root_folder_name)
        logger.info(f"Root Folder ID: {root_id}")

        if not root_id:
            logger.info("Root folder not found. Attempting creation...")
            root_id = dm.create_folder(dm.root_folder_name)
            logger.info(f"Root folder created with ID: {root_id}")
        
        # Check permissions
        logger.info(f"Verifying permissions for {root_id}...")
        perms = service.permissions().list(fileId=root_id).execute()
        for p in perms.get('permissions', []):
            logger.info(f" - Permission: {p.get('role')} for {p.get('type')}")

    except HttpError as error:
        logger.error(f"An HTTP error occurred: {error}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        import traceback
        logger.error(traceback.format_exc())

    logger.info("--- Google Drive Debug End ---")

if __name__ == "__main__":
    debug_drive()
