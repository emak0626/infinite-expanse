import os
from google_auth import get_drive_service

class DriveManager:
    def __init__(self):
        self.service = get_drive_service()
        self.root_folder_name = "📊 Infinite Expanse System"
        self.sub_folders = [
            "01_Market_Data",
            "02_AI_Daily_Reports",
            "03_Trading_Strategies",
            "04_Portfolios",
            "05_NotebookLM_Context",
            "06_Market_Context",
            "07_Market_Analysis",
            "99_System_Config"
        ]

    def get_folder_id(self, folder_name, parent_id=None):
        """Finds a folder by name and optional parent ID. Prioritizes writable folders."""
        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
        
        results = self.service.files().list(q=query, spaces='drive', fields='files(id, name, capabilities)').execute()
        items = results.get('files', [])
        
        if not items:
            print(f"Folder '{folder_name}' not found (Parent: {parent_id})")
            return None
        
        # Filter for writable folders
        for item in items:
            caps = item.get('capabilities', {})
            if caps.get('canEdit', False):
                print(f"Found writable folder '{folder_name}': {item['id']}")
                return item['id']
        
        print(f"Found folders for '{folder_name}', but none are writable. Treating as not found.")
        return None

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

    def share_with_user(self, file_id, email, role='reader'):
        """Shares a file/folder with a specific user email."""
        try:
            permission = {
                'type': 'user',
                'role': role,
                'emailAddress': email
            }
            self.service.permissions().create(
                fileId=file_id,
                body=permission,
                fields='id'
            ).execute()
            print(f"Shared {file_id} with {email} as {role}")
            return True
        except Exception as e:
            print(f"Error sharing with {email}: {e}")
            return False

    def get_root_id(self):
        """Finds or creates the root system folder."""
        root_id = self.get_folder_id(self.root_folder_name)
        if not root_id:
            root_id = self.create_folder(self.root_folder_name)
        return root_id

    def upload_file_content(self, filename, content, parent_id=None, folder_name=None, mime_type='text/markdown'):
        """Uploads or updates a file in Google Drive with the given content."""
        from googleapiclient.http import MediaInMemoryUpload
        
        # If folder_name is provided, it's relative to the root unless we have a parent_id
        if folder_name and not parent_id:
            root_id = self.get_root_id()
            parent_id = self.get_folder_id(folder_name, parent_id=root_id)
            if not parent_id:
                parent_id = self.create_folder(folder_name, parent_id=root_id)

        # Check if file already exists to update
        query = f"name = '{filename}' and trashed = false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
        
        results = self.service.files().list(q=query, spaces='drive', fields='files(id)').execute()
        items = results.get('files', [])

        media = MediaInMemoryUpload(content.encode('utf-8'), mimetype=mime_type, resumable=True)

        try:
            if items:
                # Update existing file
                file_id = items[0]['id']
                file = self.service.files().update(
                    fileId=file_id,
                    media_body=media,
                    fields='id, webViewLink'
                ).execute()
                print(f"Updated file: {filename} (ID: {file_id})")
            else:
                # Create new file
                file_metadata = {'name': filename}
                if parent_id:
                    file_metadata['parents'] = [parent_id]
                
                file = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, webViewLink'
                ).execute()
                print(f"Created file: {filename} (ID: {file.get('id')})")
        except Exception as e:
            print(f"Upload failed: {e}")
            raise e
        
        return file.get('id'), file.get('webViewLink')

    def sync_local_directory(self, local_dir, remote_parent_id, current_rel_path=""):
        """Recursively uploads all files in a local directory, preserving structure."""
        import os
        if not os.path.exists(local_dir):
            return
        
        print(f"Syncing local directory '{local_dir}' (rel: '{current_rel_path}') to Drive parent ID '{remote_parent_id}'...")
        
        # List items in current local directory
        for item in os.listdir(local_dir):
            item_path = os.path.join(local_dir, item)
            
            if os.path.isdir(item_path):
                # It's a directory: find or create in Drive
                subfolder_id = self.get_folder_id(item, parent_id=remote_parent_id)
                if not subfolder_id:
                    subfolder_id = self.create_folder(item, parent_id=remote_parent_id)
                
                # Recurse
                self.sync_local_directory(item_path, subfolder_id, os.path.join(current_rel_path, item))
            
            elif os.path.isfile(item_path):
                # It's a file: upload
                if item.endswith(('.md', '.csv', '.json', '.txt')):
                    with open(item_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    mime_type = 'text/markdown' if item.endswith('.md') else ('text/csv' if item.endswith('.csv') else 'text/plain')
                    try:
                        self.upload_file_content(item, content, parent_id=remote_parent_id, mime_type=mime_type)
                    except Exception as e:
                        print(f"Failed to sync {item}: {e}")

    def full_workspace_sync(self):
        """Syncs the entire local workspace to the cloud structure."""
        root_link, folder_map = self.setup_system_folders()
        root_id = self.get_root_id()
        
        # Local workspace mapping
        workspace_root = "workspace"
        mappings = {
            "AI_Reports": "02_AI_Daily_Reports",
            "Trading_Strategies": "03_Trading_Strategies",
            "Market_Data": "01_Market_Data",
            "Portfolios": "04_Portfolios",
            "Market_Context": "06_Market_Context",
            "Market_Analysis": "07_Market_Analysis"
        }
        
        for local_sub, remote_sub_name in mappings.items():
            local_path = os.path.join(workspace_root, local_sub)
            if not os.path.exists(local_path):
                continue
            
            # Find the ID for the mapped remote subfolder
            remote_sub_id = self.get_folder_id(remote_sub_name, parent_id=root_id)
            if not remote_sub_id:
                remote_sub_id = self.create_folder(remote_sub_name, parent_id=root_id)
            
            self.sync_local_directory(local_path, remote_sub_id)
        
        return root_link

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
