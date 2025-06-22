import streamlit as st
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import tempfile
import os
import uuid
import mimetypes
from urllib.parse import urlparse, parse_qs

# Configuration - Update these
SCOPES = ['https://www.googleapis.com/auth/drive']
FOLDER_ID = '1RNTdQpYKK-MAqO8pIsOHD3LuTWJCBKGw'
CREDENTIALS_FILE = '/Users/apple/projects/test-2/clients-webApp.json'
REDIRECT_URI = "http://localhost:8501"  # Must match your OAuth client settings

# Initialize session state
if 'auth' not in st.session_state:
    st.session_state.auth = {
        'authenticated': False,
        'state': None,
        'creds': None
    }

st.set_page_config(page_title="📤 Drive File Uploader", layout="centered")
st.title("🔐 Secure File Uploader to Google Drive")

def create_flow(state=None):
    """Create a new OAuth flow instance"""
    return Flow.from_client_secrets_file(
        CREDENTIALS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=REDIRECT_URI
    )

def authenticate():
    """Initialize the OAuth flow"""
    flow = create_flow()
    auth_url, state = flow.authorization_url(
        access_type='offline',
        prompt='consent',
        include_granted_scopes='true'
    )
    
    # Store the state in session
    st.session_state.auth['state'] = state
    st.query_params.clear()
    
    # Perform the redirect
    st.markdown(f'<meta http-equiv="refresh" content="0; url={auth_url}">', unsafe_allow_html=True)
    st.stop()

def handle_callback():
    """Handle the OAuth callback"""
    query_params = st.query_params
    if 'code' in query_params and 'state' in st.session_state.auth:
        try:
            # Recreate the flow with the stored state
            flow = create_flow(state=st.session_state.auth['state'])
            flow.fetch_token(code=query_params['code'])
            
            # Store credentials and update state
            st.session_state.auth['creds'] = flow.credentials
            st.session_state.auth['authenticated'] = True
            st.session_state.auth['state'] = None  # Clear state after use
            
            # Clear the URL parameters
            st.query_params.clear()
            
            # Rerun to refresh the page
            st.rerun()
        except Exception as e:
            st.error(f"Authentication failed: {str(e)}")
            st.stop()

# Check for callback first
handle_callback()

# Main App Logic
if not st.session_state.auth.get('authenticated', False):
    st.markdown("Login via Google → Upload any file → File is securely uploaded with restricted access.")
    st.markdown("---")
    
    if st.button("🔐 Authenticate with Google"):
        authenticate()
else:
    st.success("✅ Authenticated successfully!")
    creds = st.session_state.auth['creds']
    drive_service = build('drive', 'v3', credentials=creds)
    
    # File Upload Section
    uploaded_file = st.file_uploader("📄 Upload your file", type=None)
    
    if uploaded_file is not None:
        # Create temporary file
        unique_id = str(uuid.uuid4())
        file_ext = os.path.splitext(uploaded_file.name)[1]
        temp_path = os.path.join(tempfile.gettempdir(), f"{unique_id}{file_ext}")
        
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.success(f"✅ File saved locally as `{uploaded_file.name}`. Uploading now...")
        
        # Detect mime type
        mime_type, _ = mimetypes.guess_type(uploaded_file.name)
        mime_type = mime_type or 'application/octet-stream'
        
        # Upload to Drive
        try:
            file_metadata = {'name': uploaded_file.name, 'parents': [FOLDER_ID]}
            media = MediaFileUpload(temp_path, mimetype=mime_type)
            
            uploaded = drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id',
                supportsAllDrives=True
            ).execute()
            
            file_id = uploaded['id']
            
            # Remove inherited permissions
            try:
                permissions = drive_service.permissions().list(
                    fileId=file_id,
                    supportsAllDrives=True
                ).execute()
                
                for perm in permissions.get('permissions', []):
                    if perm['role'] != 'owner':
                        drive_service.permissions().delete(
                            fileId=file_id,
                            permissionId=perm['id'],
                            supportsAllDrives=True
                        ).execute()
            except Exception as e:
                st.warning(f"⚠️ Could not remove inherited permissions: {e}")
            
            os.remove(temp_path)
            st.balloons()
            st.success(f"🎉 `{uploaded_file.name}` uploaded successfully!")
            st.markdown(f"🔒 File ID: `{file_id}`")
            
        except Exception as e:
            st.error(f"❌ Upload failed: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    if st.button("🔓 Logout"):
        # Clear authentication state
        st.session_state.auth = {
            'authenticated': False,
            'state': None,
            'creds': None
        }
        st.rerun()