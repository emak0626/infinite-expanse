import google_auth
from googleapiclient.errors import HttpError

def test_apis():
    print("Testing Google Drive API...")
    try:
        drive_service = google_auth.get_drive_service()
        about = drive_service.about().get(fields="user").execute()
        print(f"Drive API Auth Success! Service Account Email: {about['user']['emailAddress']}")
    except HttpError as e:
        print(f"Drive API Error: {e}")
        return False
    except Exception as e:
        print(f"Unknown Error: {e}")
        return False

    print("\nTesting Google Sheets API...")
    try:
        sheets_client = google_auth.get_sheets_client()
        # This just authorizes, let's try opening a dummy spreadsheet
        print("Sheets API Auth Success! (Note: Further tests require an existing sheet ID)")
    except Exception as e:
        print(f"Sheets API Error: {e}")
        return False

    return True

if __name__ == "__main__":
    test_apis()
