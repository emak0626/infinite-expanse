import os
from google_auth import get_drive_service

class DriveManager:
    def __init__(self):
        self.service = get_drive_service()
        self.root_folder_name = "📊 Infinite Expanse System"
        self.sub_folders = [
            "01_Market_Data",
            "02_AI_Daily_Reports",
            "03_Portfolios",
            "99_System_Config"
        ]

    def get_folder_id(self, folder_name, parent_id=None):
        """Finds a folder by name and optional parent ID."""
        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
        
        results = self.service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        items = results.get('files', [])
        
        if not items:
            return None
        return items[0]['id']

    def create_folder(self, folder_name, parent_id=None):
        """Creates a folder in Google Drive and shares it with anyone with link."""
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            file_metadata['parents'] = [parent_id]
        
        file = self.service.files().create(body=file_metadata, fields='id, webViewLink').execute()
        folder_id = file.get('id')
        web_link = file.get('webViewLink')
        print(f"Created folder: {folder_name} (ID: {folder_id})")
        
        # Share with anyone with link
        self.share_with_anyone(folder_id)
        
        return folder_id

    def share_with_anyone(self, file_id):
        """Shares the file/folder with anyone with the link (reader)."""
        try:
            permission = {
                'type': 'anyone',
                'role': 'reader'
            }
            self.service.permissions().create(
                fileId=file_id,
                body=permission
            ).execute()
            print(f"Set 'anyone with link' reader permission for: {file_id}")
        except Exception as e:
            print(f"Error sharing file {file_id}: {e}")

    def setup_system_folders(self):
        """Sets up the entire system folder structure."""
        print(f"Setting up system folders in Google Drive...")
        
        # 1. Parent folder
        root_id = self.get_folder_id(self.root_folder_name)
        if not root_id:
            root_id = self.create_folder(self.root_folder_name)
        
        root_link = self.get_web_link(self.root_folder_name)

        # 2. Sub folders
        link_map = {}
        for sub in self.sub_folders:
            sub_id = self.get_folder_id(sub, parent_id=root_id)
            if not sub_id:
                sub_id = self.create_folder(sub, parent_id=root_id)
            
            link = self.get_web_link(sub, parent_id=root_id)
            link_map[sub] = link
        
        return root_link, link_map

    def get_web_link(self, name, parent_id=None):
        """Retrieves the webViewLink for a given file/folder name."""
        query = f"name = '{name}' and trashed = false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
        
        results = self.service.files().list(q=query, spaces='drive', fields='files(id, name, webViewLink)').execute()
        items = results.get('files', [])
        
        if not items:
            return None
        return items[0].get('webViewLink')

if __name__ == "__main__":
    manager = DriveManager()
    manager.setup_system_folders()
    print(f"Root Link: {manager.get_web_link(manager.root_folder_name)}")
