import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import TELEGRAM_BOT_TOKEN, SUPER_ADMIN_IDS, logger
from database import (
    registrar_o_actualizar_usuario,
    obtener_usuario,
    obtener_categorias_activas,
    obtener_materiales_por_categoria,
    obtener_material_por_id,
    crear_solicitud,
    obtener_solicitud_completa,
    responder_solicitud,
)
from excel_generator import generar_vale_excel
from drive_service import subir_excel_a_drive

SELECCIONANDO_CATEGORIA, SELECCIONANDO_MATERIAL, INGRESANDO_CANTIDAD, CONFIRMANDO_CARRITO = range(4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # 1. Registrar o actualizar al técnico en MySQL
    try:
        await registrar_o_actualizar_usuario(
            telegram_id=user.id,
            nombre=user.full_name,
            username=user.username
        )
    except Exception as e:
        logger.error(f"Error al registrar usuario: {e}")

    # 2. Reiniciar el carrito para la nueva sesión
    context.user_data['cart'] = []

    try:
        # 3. Obtener las categorías activas
        categorias = await obtener_categorias_activas()
        if not categorias:
            text_error = "❌ No hay categorías activas disponibles en el catálogo en este momento."
            if update.message:
                await update.message.reply_text(text_error)
            elif update.callback_query:
                await update.callback_query.answer()
                await update.callback_query.edit_message_text(text_error)
            return ConversationHandler.END

        # 4. Crear teclado directo con las categorías + botón Cancelar
        keyboard = [
            [InlineKeyboardButton(cat['nombre'], callback_data=f"cat_{cat['id']}")] for cat in categorias
        ]
        keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")])

        text = (
            f"👋 ¡Hola, **{user.first_name}**!\n\n"
            "Bienvenido al sistema de solicitudes de material de **Zooy / Fibra a la Casa**.\n\n"
            "📁 **Selecciona una categoría para armar tu vale:**"
        )
        
        if update.message:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        elif update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

        # 5. Pasar inmediatamente al estado de selección de categoría
        return SELECCIONANDO_CATEGORIA

    except Exception as e:
        logger.error(f"Error en start: {e}")
        text_fail = "⚠️ Ocurrió un error al conectar con la base de datos de materiales."
        if update.message:
            await update.message.reply_text(text_fail)
        elif update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text_fail)
        return ConversationHandler.END
    
async def iniciar_solicitud(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        categorias = await obtener_categorias_activas()
        if not categorias:
            await query.edit_message_text("❌ No hay categorías activas disponibles en este momento.")
            return ConversationHandler.END

        keyboard = [
            [InlineKeyboardButton(cat['nombre'], callback_data=f"cat_{cat['id']}")] for cat in categorias
        ]
        keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")])

        await query.edit_message_text("📁 Selecciona una categoría:", reply_markup=InlineKeyboardMarkup(keyboard))
        return SELECCIONANDO_CATEGORIA
    except Exception as e:
        logger.error(f"Error en iniciar_solicitud: {e}")
        await query.edit_message_text("⚠️ Ocurrió un error al conectar con la base de datos.")
        return ConversationHandler.END



async def seleccionar_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancelar":
        await query.edit_message_text("🚫 Solicitud cancelada.")
        return ConversationHandler.END

    try:
        # Extraer el ID de la categoría (ejemplo 'cat_1' -> 1)
        cat_id = int(query.data.split("_")[1])
        context.user_data['current_cat_id'] = cat_id

        materiales = await obtener_materiales_por_categoria(cat_id)

        if not materiales:
            keyboard = [[InlineKeyboardButton("🔙 Volver a Categorías", callback_data="iniciar_solicitud")]]
            await query.edit_message_text("⚠️ No hay materiales en esta categoría.", reply_markup=InlineKeyboardMarkup(keyboard))
            return SELECCIONANDO_CATEGORIA

        # Construir teclado
        keyboard = []
        for mat in materiales:
            # Soporte por si devuelve dict o tupla
            mat_id = mat['id'] if isinstance(mat, dict) else mat[0]
            mat_sku = mat['sku'] if isinstance(mat, dict) else mat[1]
            mat_nombre = mat['nombre'] if isinstance(mat, dict) else mat[2]

            btn_text = f"{mat_nombre} ({mat_sku})"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"mat_{mat_id}")])

        keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="iniciar_solicitud")])

        await query.edit_message_text("📦 Selecciona un material:", reply_markup=InlineKeyboardMarkup(keyboard))
        return SELECCIONANDO_MATERIAL

    except Exception as e:
        logger.error(f"Error en seleccionar_categoria: {e}", exc_info=True)
        await query.edit_message_text("❌ Error al cargar los materiales. Intenta de nuevo.")
        return ConversationHandler.END



async def seleccionar_material(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "iniciar_solicitud":
        return await iniciar_solicitud(update, context)

    try:
        mat_id = int(query.data.split("_")[1])
        material = await obtener_material_por_id(mat_id)
        context.user_data['selected_material'] = material

        await query.edit_message_text(
            f"🔢 Ingresa la cantidad deseada para:\n"
            f"**{material['nombre']}** ({material['sku']})\n"
            f"Unidad de Medida: `{material['unidad']}`",
            parse_mode="Markdown"
        )
        return INGRESANDO_CANTIDAD
    except Exception as e:
        logger.error(f"Error en seleccionar_material: {e}")
        await query.edit_message_text("❌ Error al procesar el material.")
        return ConversationHandler.END

async def ingresar_cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()

    try:
        cantidad = float(texto)
        if cantidad <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ Por favor, ingresa un número mayor a 0.")
        return INGRESANDO_CANTIDAD

    material = context.user_data.get('selected_material')
    cart = context.user_data.get('cart', [])

    cart.append({
        'material_id': material['id'],
        'sku': material['sku'],
        'descripcion': material['nombre'],
        'cantidad': cantidad,
        'unidad': material['unidad']
    })
    context.user_data['cart'] = cart

    return await mostrar_resumen_carrito(update, context)

async def mostrar_resumen_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cart = context.user_data.get('cart', [])

    resumen = "🛒 **Resumen de tu Carrito:**\n\n"
    for idx, item in enumerate(cart, 1):
        resumen += f"{idx}. **{item['descripcion']}** ({item['sku']})\n"
        resumen += f"   Cantidad: `{item['cantidad']} {item['unidad']}`\n"

    keyboard = [
        [InlineKeyboardButton("➕ Agregar más materiales", callback_data="iniciar_solicitud")],
        [InlineKeyboardButton("✅ Confirmar y Enviar Solicitud", callback_data="confirmar_solicitud")],
        [InlineKeyboardButton("❌ Cancelar Solicitud", callback_data="cancelar")]
    ]

    if update.callback_query:
        await update.callback_query.edit_message_text(resumen, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.message.reply_text(resumen, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    return CONFIRMANDO_CARRITO

async def procesar_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "iniciar_solicitud":
        return await iniciar_solicitud(update, context)

    if query.data == "cancelar":
        context.user_data['cart'] = []
        await query.edit_message_text("🚫 Solicitud cancelada y carrito vaciado.")
        return ConversationHandler.END

    if query.data == "confirmar_solicitud":
        user = update.effective_user
        cart = context.user_data.get('cart', [])

        if not cart:
            await query.edit_message_text("⚠️ El carrito está vacío.")
            return ConversationHandler.END

        try:
            solicitud_id = await crear_solicitud(
                usuario_telegram_id=user.id,
                tecnico_telegram_id=user.id,
                items=cart,
                area="PLEX"
            )

            context.user_data['cart'] = []

            await query.edit_message_text(
                f"✅ **¡Solicitud enviada exitosamente!**\n\n"
                f"📄 **Folio:** `#SOL-{solicitud_id}`\n"
                f"⏳ Estado: **Pendiente de aprobación**\n\n"
                f"Te notificaremos cuando un administrador revise tu pedido.",
                parse_mode="Markdown"
            )

            msg_admin = (
                f"🔔 **NUEVA SOLICITUD DE MATERIAL**\n\n"
                f"📄 **Folio:** `#SOL-{solicitud_id}`\n"
                f"👤 **Técnico:** {user.full_name} (@{user.username or 'S/A'})\n"
                f"🏢 **Área:** PLEX\n\n"
                f"📋 **Items:**\n"
            )
            for item in cart:
                msg_admin += f"• {item['sku']} - {item['descripcion']} x `{item['cantidad']} {item['unidad']}`\n"

            keyboard_admin = [[
                InlineKeyboardButton("✅ Aprobar", callback_data=f"admin_aprobar_{solicitud_id}"),
                InlineKeyboardButton("❌ Rechazar", callback_data=f"admin_rechazar_{solicitud_id}")
            ]]

            for admin_id in SUPER_ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=msg_admin,
                        reply_markup=InlineKeyboardMarkup(keyboard_admin),
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Error notificando al admin {admin_id}: {e}")

        except Exception as e:
            logger.error(f"Error al guardar la solicitud: {e}")
            await query.edit_message_text("❌ Ocurrió un error al guardar tu solicitud en el sistema.")

        return ConversationHandler.END

async def procesar_respuesta_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    partes = data.split("_")
    accion = partes[1]
    solicitud_id = int(partes[2])

    admin_user = update.effective_user

    user_db = await obtener_usuario(admin_user.id)
    if not user_db or user_db['rol'] != 'admin':
        await query.edit_message_text("❌ No tienes permisos de administrador para realizar esta acción.")
        return

    solicitud = await obtener_solicitud_completa(solicitud_id)
    if not solicitud:
        await query.edit_message_text("❌ La solicitud no existe.")
        return

    if solicitud['estado'] != 'pendiente':
        await query.edit_message_text(f"⚠️ Esta solicitud ya fue procesada anteriormente ({solicitud['estado'].upper()}).")
        return

    nuevo_estado = 'aprobada' if accion == 'aprobar' else 'rechazada'
    exito = await responder_solicitud(solicitud_id, admin_user.id, nuevo_estado)

    if not exito:
        await query.edit_message_text("⚠️ No se pudo procesar la solicitud.")
        return

    emoji = "✅" if nuevo_estado == 'aprobada' else "❌"

    ruta_excel = None
    link_drive = None

    # 1. Si es APROBADA, generamos el Excel y lo subimos a Google Drive para el ADMIN
    if nuevo_estado == 'aprobada':
        try:
            ruta_excel = generar_vale_excel(solicitud)
            link_drive = subir_excel_a_drive(ruta_excel)
        except Exception as e:
            logger.error(f"Error generando Excel o subiendo a Drive: {e}")

    # 2. Actualizar el mensaje del Administrador en Telegram
    msg_admin_edit = (
        f"{query.message.text}\n\n"
        f"----------------------------------------\n"
        f"{emoji} **Solicitud {nuevo_estado.upper()}** por {admin_user.full_name}."
    )

    keyboard_admin = []
    if link_drive:
        keyboard_admin.append([InlineKeyboardButton("🌐 Abrir/Descargar en Google Drive", url=link_drive)])

    await query.edit_message_text(
        text=msg_admin_edit,
        reply_markup=InlineKeyboardMarkup(keyboard_admin) if keyboard_admin else None,
        parse_mode="Markdown"
    )

    # 3. Enviar el archivo físico (.xlsx) al Administrador que aprobó
    if ruta_excel and os.path.exists(ruta_excel):
        try:
            with open(ruta_excel, 'rb') as doc:
                await context.bot.send_document(
                    chat_id=admin_user.id,
                    document=doc,
                    filename=os.path.basename(ruta_excel),
                    caption=f"📄 **Vale de Movimiento generado para la solicitud `#SOL-{solicitud_id}`**",
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"Error enviando el archivo Excel al admin: {e}")

    # 4. NOTIFICACIÓN SIMPLE AL TÉCNICO (Sin archivos ni links de Drive)
    msg_tecnico = (
        f"🔔 **ACTUALIZACIÓN DE SOLICITUD** `#SOL-{solicitud_id}`\n\n"
        f"Tu solicitud ha sido **{nuevo_estado.upper()}** {emoji}\n"
        f"👮 **Atendido por:** {admin_user.full_name}\n"
    )

    try:
        await context.bot.send_message(
            chat_id=solicitud['tecnico_id'],
            text=msg_tecnico,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error notificando al técnico: {e}")


def main():
    logger.info("Iniciando Bot de Materiales...")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(iniciar_solicitud, pattern="^iniciar_solicitud$")
        ],
        states={
            SELECCIONANDO_CATEGORIA: [
                CallbackQueryHandler(seleccionar_categoria, pattern="^(cat_\d+|cancelar)$"),
                CallbackQueryHandler(iniciar_solicitud, pattern="^iniciar_solicitud$")
            ],
            SELECCIONANDO_MATERIAL: [
                CallbackQueryHandler(seleccionar_material, pattern="^(mat_\d+|iniciar_solicitud)$"),
                CallbackQueryHandler(iniciar_solicitud, pattern="^iniciar_solicitud$")
            ],
            INGRESANDO_CANTIDAD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ingresar_cantidad)
            ],
            CONFIRMANDO_CARRITO: [
                CallbackQueryHandler(procesar_carrito, pattern="^(iniciar_solicitud|confirmar_solicitud|cancelar)$")
            ]
        },
        fallbacks=[CommandHandler('start', start)],
        per_chat=True,
        per_user=True,
        per_message=False
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(procesar_respuesta_admin, pattern="^admin_"))

    logger.info("Bot en ejecución...")
    app.run_polling()

if __name__ == '__main__':
    main()