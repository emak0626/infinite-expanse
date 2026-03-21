from google_auth import get_sheets_client
import pandas as pd

class SheetsManager:
    def __init__(self):
        self.client = get_sheets_client()

    def get_or_create_spreadsheet(self, title, folder_id=None):
        """Opens an existing spreadsheet or creates a new one inside a folder."""
        try:
            spreadsheet = self.client.open(title)
            print(f"Opened existing spreadsheet: {title}")
        except Exception as e:
            print(f"Could not open spreadsheet '{title}': {e}. Attempting to create new one.")
            spreadsheet = self.client.create(title)
            print(f"Created new spreadsheet: {title}")
            
            # If folder_id is provided, move the file to the folder
            if folder_id:
                from google_auth import get_drive_service
                drive_service = get_drive_service()
                file_id = spreadsheet.id
                # Retrieve the existing parents to remove
                file = drive_service.files().get(fileId=file_id, fields='parents').execute()
                previous_parents = ",".join(file.get('parents'))
                # Move the file to the new folder
                drive_service.files().update(
                    fileId=file_id,
                    addParents=folder_id,
                    removeParents=previous_parents,
                    fields='id, parents'
                ).execute()
                print(f"Moved spreadsheet to folder ID: {folder_id}")
                
        return spreadsheet

    def write_dataframe(self, spreadsheet_title, sheet_name, df, folder_id=None):
        """Writes a Pandas DataFrame to a specific sheet in a spreadsheet."""
        spreadsheet = self.get_or_create_spreadsheet(spreadsheet_title, folder_id)
        
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except Exception:
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="100", cols="20")
        
        # Clear existing content
        worksheet.clear()
        
        # Prepare data with header
        data = [df.columns.values.tolist()] + df.values.tolist()
        
        # Update sheet
        worksheet.update('A1', data)
        print(f"Successfully wrote {len(df)} rows to {spreadsheet_title} -> {sheet_name}")

if __name__ == "__main__":
    # Test with dummy data
    manager = SheetsManager()
    test_df = pd.DataFrame({
        'Stock Code': ['7203', '9984', '6758'],
        'Name': ['Toyota', 'SoftBank', 'Sony'],
        'AI Score': [85, 92, 78]
    })
    manager.write_dataframe("Test Market Data", "Daily_Ranking", test_df)
