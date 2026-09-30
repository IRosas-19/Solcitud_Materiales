import os
import openpyxl
from openpyxl.cell.cell import Cell
from datetime import datetime, timedelta
from config import TEMPLATE_EXCEL_PATH, OUTPUT_DIR, logger

def escribir_celda_segura(sheet, coordenada: str, valor):
    """
    Escribe un valor en una celda respetando los rangos combinados (Merged Cells).
    """
    celda = sheet[coordenada]
    
    if not isinstance(celda, Cell):
        for merged_range in sheet.merged_cells.ranges:
            if coordenada in merged_range:
                top_left_coord = merged_range.start_cell.coordinate
                sheet[top_left_coord] = valor
                return
    else:
        sheet[coordenada] = valor

def generar_vale_excel(solicitud: dict) -> str:
    """
    Genera el archivo Excel rellenando la plantilla oficial con los datos de la solicitud.
    """
    if not os.path.exists(TEMPLATE_EXCEL_PATH):
        logger.error(f"No se encontró la plantilla Excel en: {TEMPLATE_EXCEL_PATH}")
        raise FileNotFoundError(f"Plantilla no encontrada: {TEMPLATE_EXCEL_PATH}")

    wb = openpyxl.load_workbook(TEMPLATE_EXCEL_PATH)
    sheet = wb.active

    # 1. Fechas y Cabecera
    ahora = datetime.now()
    fecha_solicitud_str = ahora.strftime("%d/%m/%Y")
    
    fecha_entrega = ahora + timedelta(days=1)
    fecha_entrega_str = fecha_entrega.strftime("%d/%m/%Y")

    tecnico = solicitud.get('tecnico_nombre', 'N/A')
    area = solicitud.get('area', 'PLEX')

    # Marcamos casilla 'Salida'
    escribir_celda_segura(sheet, 'E6', 'X')

    # Mapeo a las celdas correctas
    escribir_celda_segura(sheet, 'D9', tecnico)              # Solicita
    escribir_celda_segura(sheet, 'I8', area)                 # Área
    escribir_celda_segura(sheet, 'P8', fecha_solicitud_str)    # Fecha de solicitud
    escribir_celda_segura(sheet, 'P9', fecha_entrega_str)      # Fecha de entrega (+1 día)

    # 2. Renglones / Materiales (Inicia en fila 12)
    FILA_INICIO = 12

    items = solicitud.get('items', [])
    for idx, item in enumerate(items):
        fila_actual = FILA_INICIO + idx

        escribir_celda_segura(sheet, f'C{fila_actual}', item['sku'])          # SKU
        escribir_celda_segura(sheet, f'E{fila_actual}', item['descripcion'])  # Descripción
        escribir_celda_segura(sheet, f'K{fila_actual}', item['cantidad'])     # Cantidad
        escribir_celda_segura(sheet, f'L{fila_actual}', item['unidad'])       # UM

    # 3. Guardar archivo
    folio = f"SOL-{solicitud['id']}"
    nombre_archivo = f"Vale_Movimiento_{tecnico}_{ahora.strftime('%Y%m%d')}.xlsx"
    ruta_salida = os.path.join(OUTPUT_DIR, nombre_archivo)
    
    wb.save(ruta_salida)
    logger.info(f"Vale Excel generado exitosamente: {ruta_salida}")
    
    return ruta_salida