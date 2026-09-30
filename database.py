import asyncio
from concurrent.futures import ThreadPoolExecutor
from config import db_pool, logger, SUPER_ADMIN_IDS

# ThreadPoolExecutor para ejecutar operaciones I/O de MySQL en hilos secundarios
executor = ThreadPoolExecutor(max_workers=10)

def _execute_query(query: str, params: tuple = None, fetchone: bool = False, fetchall: bool = False):
    """Función síncrona auxiliar para obtener una conexión del pool y ejecutar una consulta."""
    if not db_pool:
        raise Exception("El pool de base de datos no está inicializado.")
    
    conn = db_pool.connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params or ())
            if fetchone:
                return cursor.fetchone()
            if fetchall:
                return cursor.fetchall()
            return cursor.lastrowid
    finally:
        conn.close()

async def run_async(func, *args, **kwargs):
    """Ejecuta una función síncrona dentro del ThreadPoolExecutor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, lambda: func(*args, **kwargs))

# ==========================================
# GESTIÓN DE USUARIOS
# ==========================================

async def registrar_o_actualizar_usuario(telegram_id: int, nombre: str, username: str = None) -> dict:
    """Registra o actualiza los datos del usuario."""
    rol = 'admin' if telegram_id in SUPER_ADMIN_IDS else 'tecnico'
    
    query = """
        INSERT INTO usuarios (telegram_id, nombre, username, rol)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            nombre = VALUES(nombre),
            username = VALUES(username)
    """
    await run_async(_execute_query, query, (telegram_id, nombre, username, rol))
    return await obtener_usuario(telegram_id)


async def obtener_usuario(telegram_id: int) -> dict:
    """Obtiene los datos de un usuario por su Telegram ID."""
    query = "SELECT telegram_id, nombre, username, rol, activo FROM usuarios WHERE telegram_id = %s"
    user = await run_async(_execute_query, query, (telegram_id,), fetchone=True)
    
    # Si el ID está en SUPER_ADMIN_IDS, forzamos el rol a 'admin'
    if user and telegram_id in SUPER_ADMIN_IDS:
        user['rol'] = 'admin'
    return user

# ==========================================
# CATALOGO DE MATERIALES
# ==========================================

async def obtener_categorias_activas() -> list[dict]:
    """Obtiene todas las categorías activas que tengan materiales activos."""
    query = """
        SELECT DISTINCT c.id, c.nombre 
        FROM categorias c
        INNER JOIN materiales m ON c.id = m.categoria_id
        WHERE c.activa = TRUE AND m.activo = TRUE
        ORDER BY c.nombre ASC
    """
    return await run_async(_execute_query, query, fetchall=True)

async def obtener_materiales_por_categoria(categoria_id: int) -> list[dict]:
    """Obtiene todos los materiales activos de una categoría específica."""
    query = """
        SELECT id, categoria_id, sku, nombre, unidad
        FROM materiales
        WHERE categoria_id = %s AND activo = 1
        ORDER BY nombre ASC
    """
    return await run_async(_execute_query, query, (categoria_id,), fetchall=True)

async def obtener_material_por_id(material_id: int) -> dict:
    """Obtiene la información general de un material."""
    query = "SELECT id, sku, nombre, unidad FROM materiales WHERE id = %s"
    return await run_async(_execute_query, query, (material_id,), fetchone=True)

# ==========================================
# SOLICITUDES Y DETALLE
# ==========================================

async def crear_solicitud(usuario_telegram_id: int, tecnico_telegram_id: int, items: list[dict], area: str = 'PLEX') -> int:
    """
    Crea la cabecera de la solicitud y sus renglones en la tabla detalle.
    items esperados: [{'material_id': int, 'cantidad': float}]
    """
    query_cabecera = """
        INSERT INTO solicitudes (usuario_telegram_id, tecnico_telegram_id, area, estado)
        VALUES (%s, %s, %s, 'pendiente')
    """
    solicitud_id = await run_async(_execute_query, query_cabecera, (usuario_telegram_id, tecnico_telegram_id, area))
    
    query_detalle = """
        INSERT INTO solicitud_detalle (solicitud_id, material_id, cantidad)
        VALUES (%s, %s, %s)
    """
    for item in items:
        await run_async(_execute_query, query_detalle, (solicitud_id, item['material_id'], item['cantidad']))
        
    return solicitud_id

async def responder_solicitud(solicitud_id: int, admin_telegram_id: int, nuevo_estado: str, observaciones: str = None) -> bool:
    """
    Actualiza el estado de una solicitud ('aprobada' o 'rechazada') con control de concurrencia.
    Retorna True si la actualización tuvo éxito (si estaba en estado 'pendiente').
    """
    query = """
        UPDATE solicitudes
        SET estado = %s,
            fecha_respuesta = NOW(),
            respondido_por = %s,
            observaciones = %s
        WHERE id = %s AND estado = 'pendiente'
    """
    conn = db_pool.connection()
    try:
        with conn.cursor() as cursor:
            affected = cursor.execute(query, (nuevo_estado, admin_telegram_id, observaciones, solicitud_id))
            return affected > 0
    finally:
        conn.close()

async def obtener_solicitud_completa(solicitud_id: int) -> dict:
    """Obtiene la cabecera y el desglose de materiales de una solicitud para generar el reporte Excel."""
    query_cabecera = """
        SELECT 
            s.id, s.area, s.estado, s.fecha_creacion, s.fecha_respuesta, s.observaciones,
            u_sol.nombre AS solicitante_nombre, u_sol.telegram_id AS solicitante_id,
            u_tec.nombre AS tecnico_nombre, u_tec.telegram_id AS tecnico_id,
            u_adm.nombre AS admin_nombre
        FROM solicitudes s
        INNER JOIN usuarios u_sol ON s.usuario_telegram_id = u_sol.telegram_id
        INNER JOIN usuarios u_tec ON s.tecnico_telegram_id = u_tec.telegram_id
        LEFT JOIN usuarios u_adm ON s.respondido_por = u_adm.telegram_id
        WHERE s.id = %s
    """
    cabecera = await run_async(_execute_query, query_cabecera, (solicitud_id,), fetchone=True)
    if not cabecera:
        return None

    query_detalle = """
        SELECT 
            sd.cantidad,
            m.sku,
            m.nombre AS descripcion,
            m.unidad
        FROM solicitud_detalle sd
        INNER JOIN materiales m ON sd.material_id = m.id
        WHERE sd.solicitud_id = %s
    """
    detalle = await run_async(_execute_query, query_detalle, (solicitud_id,), fetchall=True)
    cabecera['items'] = detalle
    return cabecera