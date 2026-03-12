from kabu_api import KabuApiClient
from config import settings
import sys

def test_connection():
    print(f"--- API Connection Test (Auto-Discovery) ---")
    
    ports = [18080, 18081]
    password = settings.KABU_API_PASSWORD
    print(f"Loaded password starts with: {password[:2]}... (length: {len(password)})")
    
    for port in ports:
        print(f"\n--- Trying port {port} ---")
        client = KabuApiClient(mock_mode=False)
        client.base_url = f"http://localhost:{port}/kabusapi"
        
        try:
            # Example symbol (TOYOTA)
            symbol = "7203"
            print(f"Fetching board data for {symbol} using port {port}...")
            data = client.get_board(symbol)
            
            if "Mock" not in data.symbolname:
                print(f"Successfully connected to REAL API on port {port}!")
                print(f"Symbol: {data.symbolname} ({data.symbol})")
                print(f"Current Price: {data.currentprice}")
                return # Exit on first success
            else:
                print(f"Port {port} responded but returned mock data (likely due to error during fetch).")
                
        except Exception as e:
            print(f"Failed to connect to port {port}: {e}")
            
    print("\n[!] All attempts failed. Please ensure Kabu Station is running and API is enabled.")
    print("Check if the port is 'Standard' (usually 18080/18081) or if you are using HTTPS (443).")

if __name__ == "__main__":
    test_connection()
