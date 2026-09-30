import pandas as pd
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

# Conexión a la BD
connection = pymysql.connect(
    host=os.getenv("DB_HOST", "172.25.30.123"),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", "Conejos19*").strip(),
    database=os.getenv("DB_NAME", "materiales_zooy_db"),
    port=int(os.getenv("DB_PORT", 3306)),
    autocommit=True
)

excel_path = 'stock_27.xlsx'
df_raw = pd.read_excel(excel_path)

# Las cabeceras inician en la fila 3 del Excel
data_df = df_raw.iloc[4:].copy()
data_df.columns = df_raw.iloc[3].values

with connection.cursor() as cursor:
    # 1. Crear tablas si no existen
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categorias (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nombre VARCHAR(150) NOT NULL UNIQUE,
            activa BOOLEAN DEFAULT TRUE
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS materiales (
            id INT AUTO_INCREMENT PRIMARY KEY,
            categoria_id INT,
            sku VARCHAR(100) UNIQUE,
            nombre VARCHAR(255) NOT NULL,
            unidad VARCHAR(50) DEFAULT 'PIEZA',
            activo BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (categoria_id) REFERENCES categorias(id)
        );
    """)

    current_category_id = None

    for idx, row in data_df.iterrows():
        sku = str(row['SKU']).strip() if pd.notna(row['SKU']) else None
        prod = str(row['Producto']).strip() if pd.notna(row['Producto']) else None
        unidad = str(row['Unidad']).strip() if pd.notna(row['Unidad']) else 'PIEZA'

        # Identificar Fila de Categoría
        if sku and not prod:
            cat_nombre = sku
            cursor.execute(
                "INSERT INTO categorias (nombre) VALUES (%s) ON DUPLICATE KEY UPDATE nombre=%s",
                (cat_nombre, cat_nombre)
            )
            cursor.execute("SELECT id FROM categorias WHERE nombre = %s", (cat_nombre,))
            current_category_id = cursor.fetchone()[0]

        # Identificar Fila de Material
        elif sku and prod and current_category_id:
            cursor.execute("""
                INSERT INTO materiales (categoria_id, sku, nombre, unidad)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE nombre=%s, unidad=%s, categoria_id=%s
            """, (current_category_id, sku, prod, unidad, prod, unidad, current_category_id))

print("✅ Base de datos poblada exitosamente desde stock_27.xlsx")
connection.close()