import asyncio
import json
from bulk_screener import BulkScreener
from kabu_api import KabuApiClient

async def verify_scan():
    screener = BulkScreener()
    
    print("--- Testing 'growth' strategy SCAN ---")
    res_growth = await screener.run_technical_scan(strategy="growth")
    print(f"Growth Scan Result: {res_growth}")
    
    # Check if growth stocks are in results (mock mode should return growth stocks list)
    with open("workspace/Market_Data/Market_Scan_Results.csv", "r", encoding="utf-8") as f:
        content = f.read()
        # Representative growth stock from the new list
        if "5253" in content or "4478" in content:
            print("SUCCESS: Growth stocks found in CSV.")
        else:
            print("FAILURE: Growth stocks not found in CSV.")

    print("\n--- Testing 'standard' strategy SCAN ---")
    res_standard = await screener.run_technical_scan(strategy="standard")
    print(f"Standard Scan Result: {res_standard}")
    
    with open("workspace/Market_Data/Market_Scan_Results.csv", "r", encoding="utf-8") as f:
        content = f.read()
        if "2702" in content or "7532" in content:
            print("SUCCESS: Standard stocks found in CSV.")
        else:
            print("FAILURE: Standard stocks not found in CSV.")

    print("\n--- Testing 'short' (default) strategy SCAN ---")
    res_short = await screener.run_technical_scan(strategy="short")
    print(f"Short Scan Result: {res_short}")
    
    with open("workspace/Market_Data/Market_Scan_Results.csv", "r", encoding="utf-8") as f:
        content = f.read()
        # Should include Prime stocks
        if "7203" in content or "9984" in content:
            print("SUCCESS: Prime stocks found in CSV.")
        else:
            print("FAILURE: Prime stocks not found in CSV.")

if __name__ == "__main__":
    asyncio.run(verify_scan())
