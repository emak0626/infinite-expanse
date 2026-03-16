import os
import shutil
from datetime import datetime
import pandas as pd

class LocalWorkspaceManager:
    def __init__(self, base_dir="workspace"):
        self.base_dir = base_dir
        self.sub_folders = {
            "market": "Market_Data",
            "reports": "AI_Reports",
            "system": "System_Config"
        }
        self._ensure_structure()

    def _ensure_structure(self):
        """Creates the directory structure if it doesn't exist."""
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
        
        for folder_name in self.sub_folders.values():
            path = os.path.join(self.base_dir, folder_name)
            if not os.path.exists(path):
                os.makedirs(path)

    def get_path(self, category, filename):
        """Returns the absolute path for a file in a given category."""
        folder = self.sub_folders.get(category, "Misc")
        return os.path.join(os.getcwd(), self.base_dir, folder, filename)

    def save_csv(self, df, filename):
        """Saves a DataFrame as a CSV file in the Market_Data folder."""
        path = self.get_path("market", filename)
        df.to_csv(path, index=False, encoding='utf-8-sig') # UTF-8 with BOM for Excel compat
        return path

    def save_report(self, title, content):
        """Saves markdown content as a file in the AI_Reports folder."""
        # Sanitize filename
        safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '.', '_', '-')]).rstrip()
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M')}_{safe_title}.md"
        path = self.get_path("reports", filename)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return path

    def list_files(self, category=None):
        """Lists files in a given category folder."""
        files_list = []
        target_folders = [self.sub_folders[category]] if category else self.sub_folders.values()
        
        for folder in target_folders:
            folder_path = os.path.join(self.base_dir, folder)
            if not os.path.exists(folder_path): continue
            
            for f in os.listdir(folder_path):
                f_path = os.path.join(folder_path, f)
                stats = os.stat(f_path)
                files_list.append({
                    "name": f,
                    "category": folder,
                    "path": f"/workspace/{folder}/{f}",
                    "size": stats.st_size,
                    "mtime": datetime.fromtimestamp(stats.st_mtime).isoformat()
                })
        
        # Sort by modification time descending
        return sorted(files_list, key=lambda x: x['mtime'], reverse=True)

workspace_mgr = LocalWorkspaceManager()
