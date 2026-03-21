import os
import shutil
import time
from datetime import datetime, timezone, timedelta
import pandas as pd

class LocalWorkspaceManager:
    def __init__(self, base_dir="workspace"):
        self.base_dir = base_dir
        self.sub_folders = {
            "market": "Market_Data",
            "reports": "AI_Reports",
            "system": "System_Config",
            "trash": "Trash"
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
        
        jst = timezone(timedelta(hours=9))

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
                    "mtime": datetime.fromtimestamp(stats.st_mtime, tz=jst).isoformat()
                })
        
        # Sort by modification time descending
        return sorted(files_list, key=lambda x: x['mtime'], reverse=True)

    def move_to_trash(self, relative_path):
        """Moves a file from its current location to the Trash folder using a relative path like /workspace/AI_Reports/f1.md"""
        # Extract path relative to base_dir
        # Assuming relative_path starts with /workspace/
        clean_rel = relative_path.strip('/')
        parts = clean_rel.split('/')
        
        if len(parts) < 2 or parts[0] != self.base_dir:
            return False
            
        # Reconstruct source path relative to CWD
        src_path = os.path.join(os.getcwd(), *parts)
        filename = parts[-1]
        dest_path = self.get_path("trash", filename)
        
        if os.path.exists(src_path):
            # If destination exists, add a timestamp to avoid overwrite
            if os.path.exists(dest_path):
                ext = ".md" if filename.endswith(".md") else ".csv" if filename.endswith(".csv") else ""
                dest_path = dest_path.replace(ext, f"_{int(time.time())}{ext}")
            
            os.rename(src_path, dest_path)
            return True
        return False

    def delete_file(self, relative_path):
        """Permanently deletes a file (relative path starting with /workspace/)"""
        clean_rel = relative_path.strip('/')
        parts = clean_rel.split('/')
        
        if len(parts) < 2 or parts[0] != self.base_dir:
            return False
            
        abs_path = os.path.join(os.getcwd(), *parts)
        
        if os.path.exists(abs_path):
            os.remove(abs_path)
            return True
        return False

    def bulk_move_to_trash(self, relative_paths):
        """Moves multiple files to trash."""
        results = {"success": [], "failed": []}
        for path in relative_paths:
            if self.move_to_trash(path):
                results["success"].append(path)
            else:
                results["failed"].append(path)
        return results

    def bulk_delete(self, relative_paths):
        """Permanently deletes multiple files."""
        results = {"success": [], "failed": []}
        for path in relative_paths:
            if self.delete_file(path):
                results["success"].append(path)
            else:
                results["failed"].append(path)
        return results

workspace_mgr = LocalWorkspaceManager()
