import asyncio
import os
from scheduler import run_edinet_scan

async def main():
    print("--- Manual Info Collection Start ---")
    await run_edinet_scan()
    print("--- Manual Info Collection End ---")

if __name__ == "__main__":
    asyncio.run(main())
