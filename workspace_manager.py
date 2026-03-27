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
            "strategies": "Trading_Strategies",
            "context": "Market_Context",
            "analysis": "Market_Analysis",
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
        with open(path, 'w', encoding='utf-8-sig') as f:
            f.write(content)
        return path

    def list_files(self, category=None, start_date=None, end_date=None, pattern=None):
        """
        Lists files in a given category folder with optional filtering.
        - start_date, end_date: ISO strings (YYYY-MM-DD)
        - pattern: substring to search in filename (e.g. symbol "7203")
        """
        files_list = []
        target_folders = [self.sub_folders[category]] if category and category in self.sub_folders else self.sub_folders.values()
        
        jst = timezone(timedelta(hours=9))
        
        # Convert filter dates to datetime objects if provided
        start_dt = datetime.fromisoformat(start_date).replace(tzinfo=jst) if start_date else None
        end_dt = datetime.fromisoformat(end_date).replace(tzinfo=jst) if end_date else None
        if end_dt:
            # Shift end_dt to the end of the day
            end_dt = end_dt.replace(hour=23, minute=59, second=59)

        for folder in target_folders:
            folder_path = os.path.join(self.base_dir, folder)
            if not os.path.exists(folder_path): continue
            
            for f in os.listdir(folder_path):
                # Filter by pattern
                if pattern and pattern not in f:
                    continue
                
                f_path = os.path.join(folder_path, f)
                stats = os.stat(f_path)
                mtime_dt = datetime.fromtimestamp(stats.st_mtime, tz=jst)
                
                # Filter by date range
                if start_dt and mtime_dt < start_dt:
                    continue
                if end_dt and mtime_dt > end_dt:
                    continue

                files_list.append({
                    "name": f,
                    "category": folder,
                    "path": f"/workspace/{folder}/{f}",
                    "size": stats.st_size,
                    "mtime": mtime_dt.isoformat()
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

    def restore_file(self, relative_path):
        """Moves a file from Trash back to its likely original folder."""
        clean_rel = relative_path.strip('/')
        parts = clean_rel.split('/')
        
        if len(parts) < 2 or parts[0] != self.base_dir or parts[1] != self.sub_folders["trash"]:
            return False
            
        filename = parts[-1]
        src_path = os.path.join(os.getcwd(), *parts)
        
        # Guess original category
        target_category = "reports" # Default
        if filename.endswith(".csv"):
            target_category = "market"
        elif filename.startswith("analysis_") or "_MarketAnalysis" in filename:
            target_category = "analysis"
        elif filename.startswith("context_") or filename == "latest_context.json":
            target_category = "context"
        elif any(f in filename for f in ["config", "settings"]):
            target_category = "system"
            
        dest_path = self.get_path(target_category, filename)
        
        if os.path.exists(src_path):
            # Safe move: if dest exists, add timestamp
            if os.path.exists(dest_path):
                ext = os.path.splitext(filename)[1]
                dest_path = dest_path.replace(ext, f"_restored_{int(time.time())}{ext}")
            
            os.rename(src_path, dest_path)
            return True
        return False

    def bulk_restore(self, relative_paths):
        """Restores multiple files from trash."""
        results = {"success": [], "failed": []}
        for path in relative_paths:
            if self.restore_file(path):
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
