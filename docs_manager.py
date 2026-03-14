from google_auth import get_docs_service, get_drive_service
from datetime import datetime

class DocsManager:
    def __init__(self):
        self.docs_service = get_docs_service()
        self.drive_service = get_drive_service()

    def create_doc_from_markdown(self, title, markdown_content, folder_id=None):
        """Creates a Google Doc with the given title and content."""
        # 1. Create a blank document
        doc = self.docs_service.documents().create(body={'title': title}).execute()
        document_id = doc.get('documentId')
        print(f"Created Doc: {title} (ID: {document_id})")

        # 2. Add content to the document
        # Simple implementation: insert text as-is
        # In a more advanced version, we could parse markdown to structural updates
        requests = [
            {
                'insertText': {
                    'location': {
                        'index': 1,
                    },
                    'text': markdown_content
                }
            }
        ]
        self.docs_service.documents().batchUpdate(
            documentId=document_id, body={'requests': requests}).execute()

        # 3. Move the document to the specified folder
        if folder_id:
            # Retrieve the existing parents to remove
            file = self.drive_service.files().get(fileId=document_id, fields='parents').execute()
            previous_parents = ",".join(file.get('parents'))
            
            # Move the file
            self.drive_service.files().update(
                fileId=document_id,
                addParents=folder_id,
                removeParents=previous_parents,
                fields='id, parents'
            ).execute()
            print(f"Moved Doc to folder ID: {folder_id}")

        return document_id

if __name__ == "__main__":
    # Test
    manager = DocsManager()
    content = """
    # Deep Analysis Report
    Date: 2026-03-14
    
    ## Overview
    This is a test report generated automatically.
    
    - Market sentiment: Bullish
    - Recommended action: Buy
    """
    manager.create_doc_from_markdown(f"Test Report {datetime.now().strftime('%Y%m%d_%H%M')}", content)
