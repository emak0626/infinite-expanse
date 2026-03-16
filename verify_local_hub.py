import os
import asyncio
from workspace_manager import workspace_mgr
import pandas as pd

async def verify_local_hub():
    print("--- Local Workspace Verification ---")
    
    # 1. Test saving CSV
    df = pd.DataFrame([{"symbol": "TEST", "price": 100}])
    csv_path = workspace_mgr.save_csv(df, "Verification_Test.csv")
    print(f"CSV Saved: {csv_path}")
    
    # 2. Test saving Report
    report_path = workspace_mgr.save_report("Verification_Report", "# Test Report Content")
    print(f"Report Saved: {report_path}")
    
    # 3. Test listing
    files = workspace_mgr.list_files()
    print(f"Found {len(files)} files in workspace.")
    for f in files:
        print(f" - {f['category']}: {f['name']} ({f['path']})")
    
    if len(files) >= 2:
        print("\nSUCCESS: Local Workspace is functioning correctly.")
    else:
        print("\nFAILURE: Local Workspace did not store files properly.")
    
    print("--- End ---")

if __name__ == "__main__":
    asyncio.run(verify_local_hub())
