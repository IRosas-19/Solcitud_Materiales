import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from config import GOOGLE_DRIVE_FOLDER_ID, logger

SCOPES = ['https://www.googleapis.com/auth/drive.file']
TOKEN_PATH = 'token.json'
CLIENT_SECRET_PATH = 'client_secret.json'

def obtener_credenciales():
    creds = None
    # El archivo token.json guarda los permisos del usuario tras la primera ejecución
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
            
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
            
    return creds

def subir_excel_a_drive(ruta_local_excel: str) -> str:
    """
    Suba el archivo Excel generado a la carpeta especificada en Google Drive.
    """
    creds = obtener_credenciales()
    service = build('drive', 'v3', credentials=creds)

    nombre_archivo = os.path.basename(ruta_local_excel)
    file_metadata = {
        'name': nombre_archivo,
        'parents': [GOOGLE_DRIVE_FOLDER_ID]
    }
    
    media = MediaFileUpload(
        ruta_local_excel, 
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        resumable=True
    )
    
    archivo = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()

    link_drive = archivo.get('webViewLink')
    logger.info(f"Archivo subido a Google Drive: {link_drive}")
    return link_drive