import os
import logging
from dotenv import load_dotenv
from dbutils.pooled_db import PooledDB
import pymysql

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    logger.error("Error: TELEGRAM_BOT_TOKEN no configurado en el archivo .env")

def parse_admin_ids(env_value: str) -> list[int]:
    if not env_value:
        return []
    ids = []
    for raw_id in env_value.split(','):
        cleaned_id = raw_id.strip()
        if cleaned_id.isdigit():
            ids.append(int(cleaned_id))
    return ids

SUPER_ADMIN_IDS = parse_admin_ids(os.getenv("SUPER_ADMIN_IDS", ""))

# Conexión a la Base de Datos con valores por defecto seguros
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER", "root").strip()
DB_PASSWORD = os.getenv("DB_PASSWORD", "").strip()
DB_NAME = os.getenv("DB_NAME", "")
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", 5))

# Google Drive
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
CLIENT_SECRET_JSON_PATH = os.path.join(BASE_DIR, "client_secret.json")
TOKEN_JSON_PATH = os.path.join(BASE_DIR, "token.json")

# Pool de MySQL
try:
    db_pool = PooledDB(
        creator=pymysql,
        maxconnections=DB_POOL_SIZE,
        mincached=1,
        maxcached=3,
        blocking=True,
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )
    logger.info("Pool de conexiones a MySQL iniciado correctamente.")
except Exception as e:
    logger.error(f"Error al inicializar el pool de base de datos MySQL: {e}")
    db_pool = None

TEMPLATE_EXCEL_PATH = os.path.join(BASE_DIR, "3. VALE DE MOVIMIENTOS INTERNOS.xlsx")
OUTPUT_DIR = os.path.join(BASE_DIR, "generados")

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)