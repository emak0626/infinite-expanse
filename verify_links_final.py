import asyncio
from drive_manager import DriveManager

async def test_links():
    print("--- Intelligence Hub Link Verification ---")
    dm = DriveManager()
    
    # Trigger setup (now returns links)
    root_link, link_map = dm.setup_system_folders()
    
    print(f"Root Link: {root_link}")
    print(f"Sub-folders:")
    for name, link in link_map.items():
        print(f" - {name}: {link}")
        
    if root_link and "02_AI_Daily_Reports" in link_map:
        print("\nSUCCESS: All links retrieved correctly.")
    else:
        print("\nFAILURE: Some links are missing.")
    
    print("--- End ---")

if __name__ == "__main__":
    asyncio.run(test_links())
