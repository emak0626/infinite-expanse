import asyncio
import os
from drive_manager import DriveManager

def verify_workspace():
    print("--- Workspace Verification Start ---")
    try:
        manager = DriveManager()
        print("DriveManager initialized.")
        
        # Trigger setup
        print("Running setup_system_folders...")
        root_id, folder_map = manager.setup_system_folders()
        print(f"Root ID: {root_id}")
        print(f"Folders: {folder_map}")
        
        # Verify links
        root_link = manager.get_web_link(manager.root_folder_name)
        reports_link = manager.get_web_link("AI_Daily_Reports")
        
        print(f"Root Link: {root_link}")
        print(f"Reports Link: {reports_link}")
        
        if root_link and reports_link:
            print("VERIFICATION SUCCESS: Workspace folders and links are active.")
        else:
            print("VERIFICATION WARNING: Some links are missing.")
            
    except Exception as e:
        print(f"VERIFICATION ERROR: {e}")
        import traceback
        traceback.print_exc()

    print("--- Workspace Verification End ---")

if __name__ == "__main__":
    verify_workspace()
