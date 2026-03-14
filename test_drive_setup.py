import os
from drive_manager import DriveManager

def test_drive_setup():
    print("Starting Drive setup test...")
    try:
        manager = DriveManager()
        root_id, folder_map = manager.setup_system_folders()
        print(f"Success! Root ID: {root_id}")
        for name, fid in folder_map.items():
            print(f"  Folder: {name} -> ID: {fid}")
    except Exception as e:
        print(f"Error during Drive setup: {e}")

if __name__ == "__main__":
    test_drive_setup()
