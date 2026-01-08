import os
import pickle
import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import base64

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

class YouTubeUploader:
    def __init__(self, secrets_file=None, token_file='token.pickle'):
        if secrets_file is None:
            if os.path.exists('client_secrets.json'):
                secrets_file = 'client_secrets.json'
            elif os.path.exists('client_secret.json'):
                secrets_file = 'client_secret.json'
            else:
                secrets_file = 'client_secrets.json' # Default
        
        print(f"YouTubeUploader initialized. CWD: {os.getcwd()}")
        print(f"Selected secrets file: {os.path.abspath(secrets_file) if secrets_file else 'None'}")
        
        self.secrets_file = secrets_file
        self.token_file = token_file
        self.youtube = self._get_authenticated_service()

    def _get_authenticated_service(self):
        creds = None
        # Try loading from environment variable first (for GHA)
        token_b64 = os.getenv("YOUTUBE_TOKEN_BASE64")
        if token_b64:
            try:
                creds_data = base64.b64decode(token_b64)
                creds = pickle.loads(creds_data)
                print("Loaded YouTube credentials from environment variable.")
            except Exception as e:
                print(f"Error decoding YOUTUBE_TOKEN_BASE64: {e}")

        # Fallback to local file
        if not creds and os.path.exists(self.token_file):
            print(f"Loading credentials from {self.token_file}...")
            with open(self.token_file, 'rb') as token:
                try:
                    creds = pickle.load(token)
                except Exception as e:
                    print(f"Error loading {self.token_file}: {e}")

        # Refresh or re-authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("Refreshing YouTube access token...")
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing YouTube token: {e}")
                    creds = None

            if not creds or not creds.valid:
                # Interactive login
                if not os.path.exists(self.secrets_file):
                    print(f"Error: Secrets file '{self.secrets_file}' not found. Cannot authentication interactively.")
                    return None
                
                print(f"Starting interactive authentication using {self.secrets_file}...")
                flow = InstalledAppFlow.from_client_secrets_file(self.secrets_file, SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save the new token if we are using local file storage (priority over env var for saving?)
            # Usually we only save to file if we are running locally.
            # If we loaded from env var, we might not want to overwrite local file unless explicitly intended.
            # But here, saving to token.pickle is good for local dev cache.
            try:
                with open(self.token_file, 'wb') as token:
                    pickle.dump(creds, token)
                print(f"Saved new credentials to {self.token_file}")
            except Exception as e:
                print(f"Warning: Could not save {self.token_file}: {e}")

        return build('youtube', 'v3', credentials=creds)

    def upload_video(self, file_path, title, description, tags, category_id="25", privacy_status="public"):
        """
        Uploads a video to YouTube. Category 25 is 'News & Politics'.
        """
        if not self.youtube:
            print("YouTube service not initialized.")
            return

        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': category_id
            },
            'status': {
                'privacyStatus': privacy_status,
                'selfDeclaredMadeForKids': False
            }
        }

        media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
        request = self.youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Uploaded {int(status.progress() * 100)}%")
        
        print(f"Video uploaded successfully! ID: {response['id']}")
        return response['id']

if __name__ == "__main__":
    pass
    # Test (requires client_secrets.json)
    # uploader = YouTubeUploader()
    # uploader.upload_video("test_video.mp4", "Test Breaking News", "Summary", ["news", "breaking"])
