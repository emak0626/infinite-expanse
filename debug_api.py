from playwright.sync_api import sync_playwright
import time

def run():
    try:
        with sync_playwright() as p:
            print("Launching browser...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                http_credentials={'username': 'admin', 'password': 'infinity'}
            )
            page = context.new_page()
            
            def handle_console(msg):
                print(f"CONSOLE [{msg.type}]: {msg.text}")
                
            def handle_request(req):
                if "api/" in req.url:
                    print(f"API REQUEST: {req.method} {req.url}")
                    
            def handle_response(res):
                if "api/" in res.url:
                    print(f"API RESPONSE: {res.status} {res.url}")

            page.on("console", handle_console)
            page.on("request", handle_request)
            page.on("response", handle_response)
            
            print("Navigating to app...")
            page.goto('http://localhost:8000')
            time.sleep(2)
            
            print("Clicking Scanner tab...")
            page.click('text="スキャナー"')
            time.sleep(2)
            
            print("Selecting last_scan from dropdown...")
            page.select_option('#ranking-type', 'last_scan')
            time.sleep(3)
            
            print("Done navigating.")
            browser.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    run()
