import logging

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from config import TELEGRAM_BOT_TOKEN
from db.engine import init_db
from handlers import admin, alerts, price_alert, stats, subscription, wallet
from handlers.auto_lookup import handle_text
from handlers.start import ADMIN_MENU_KEYBOARD, USER_MENU_KEYBOARD, USER_MENU_TEXT, start
from scheduler import setup_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu:home":
        if admin.is_admin(query.from_user.id):
            await query.message.reply_text("👑 *관리자 패널*", parse_mode="MarkdownV2", reply_markup=ADMIN_MENU_KEYBOARD)
        else:
            await query.message.reply_text(USER_MENU_TEXT, parse_mode="MarkdownV2", reply_markup=USER_MENU_KEYBOARD)
    elif data == "menu:wallet":
        await wallet.show_wallets(update, context)
    elif data == "menu:stats":
        await stats.today_stats(update, context)
    elif data == "menu:price":
        await price_alert.show_price(update, context)
    elif data == "menu:plan":
        await subscription.show_plan_menu(update, context)
    elif data == "stats:monthly":
        await stats.monthly_stats(update, context)
    elif data.startswith("wallet:add:"):
        address = data.split(":", 2)[2]
        await wallet.add_wallet_from_address(update, context, address)
    elif data.startswith("wallet:delete:"):
        wallet_id = int(data.split(":")[2])
        await wallet.delete_wallet(update, context, wallet_id)
    elif data == "admin:home":
        await admin.admin_panel(update, context)
    elif data == "admin:users":
        await query.message.reply_text("유저 ID 또는 username을 `/finduser <id_or_username>` 명령으로 검색하세요\\.", parse_mode="MarkdownV2")
    elif data == "admin:scam":
        await admin.list_scam_tokens(update, context)
    elif data == "admin:stats":
        await admin.full_stats(update, context)
    elif data.startswith("admin:grant_pro:"):
        await admin.grant_pro(update, context, int(data.split(":")[2]))
    elif data.startswith("admin:demote:"):
        await admin.demote_to_free(update, context, int(data.split(":")[2]))
    elif data.startswith("admin:ban:"):
        await admin.ban_user(update, context, int(data.split(":")[2]))


async def find_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("사용법: /finduser <id_or_username>")
        return
    await admin.search_user(update, context, context.args[0])


async def add_scam_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("사용법: /addscam <contract_address>")
        return
    await admin.add_scam_token(update, context, context.args[0])


async def delete_scam_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("사용법: /delscam <contract_address>")
        return
    await admin.delete_scam_token(update, context, context.args[0])


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("사용법: /broadcast <message>")
        return
    await admin.broadcast(update, context, " ".join(context.args))


async def on_startup(application: Application) -> None:
    await init_db()
    scheduler = setup_scheduler(application.bot)
    scheduler.start()
    application.bot_data["scheduler"] = scheduler


def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(on_startup).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("wallet", wallet.show_wallets))
    application.add_handler(CommandHandler("today", stats.today_stats))
    application.add_handler(CommandHandler("monthly", stats.monthly_stats))
    application.add_handler(CommandHandler("price", price_alert.show_price))
    application.add_handler(CommandHandler("admin", admin.admin_panel))
    application.add_handler(CommandHandler("finduser", find_user_command))
    application.add_handler(CommandHandler("addscam", add_scam_command))
    application.add_handler(CommandHandler("delscam", delete_scam_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))

    application.add_handler(CallbackQueryHandler(menu_callback))

    # Address/TX-hash auto-detect must be registered before any generic text handler.
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
