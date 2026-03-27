import os
from dotenv import load_dotenv
load_dotenv()
from kabu_api import KabuApiClient

c = KabuApiClient()
try:
    print(f"Testing G (Growth):")
    res1 = c.get_ranking("1", "G")
    print(f"  Type 1 count: {len(res1)}")
except Exception as e:
    print(f"  Type 1 error: {e}")

try:
    print(f"Testing S (Standard):")
    res4 = c.get_ranking("1", "S")
    print(f"  Type 1 count: {len(res4)}")
except Exception as e:
    print(f"  Type 1 error: {e}")
