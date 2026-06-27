import logging

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from config import TELEGRAM_BOT_TOKEN
from db.engine import init_db
from handlers import admin, alerts, price_alert, stats, subscription, wallet
from handlers.auto_lookup import handle_text
from handlers.start import ADMIN_MENU_KEYBOARD, USER_MENU_KEYBOARD, USER_MENU_TEXT, start
from scheduler import setup_scheduler
from utils.respond import respond

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu:home":
        if admin.is_admin(query.from_user.id):
            await respond(update, "👑 *관리자 패널*", ADMIN_MENU_KEYBOARD)
        else:
            await respond(update, USER_MENU_TEXT, USER_MENU_KEYBOARD)
    elif data == "menu:wallet":
        await wallet.show_wallets(update, context)
    elif data == "menu:stats":
        await stats.today_stats(update, context)
    elif data == "menu:price":
        await price_alert.show_price(update, context)
    elif data == "menu:plan":
        await subscription.show_plan_menu(update, context)
    elif data == "menu:alerts":
        await alerts.show_alerts_menu(update, context)
    elif data == "menu:help":
        await respond(
            update,
            "❓ *도움말*\n━━━━━━━━━━━━━━━━━\n\n"
            "📍 트론 주소를 채팅창에 입력하면 잔액/거래내역을 즉시 조회합니다\\.\n"
            "💼 *내 지갑*에서 알림 받을 주소를 등록하세요\\.\n"
            "📊 *통계*에서 일별/월별 입출금 현황을 확인하세요\\.\n"
            "📈 *시세*에서 목표가 알림과 정기 리포트를 설정하세요\\.\n"
            "💳 *플랜 관리*에서 Pro 플랜으로 업그레이드하세요\\.",
        )
    elif data == "stats:monthly":
        await stats.monthly_stats(update, context)
    elif data.startswith("stats:monthly:"):
        year_month = data.split(":", 2)[2]
        year_str, month_str = year_month.split("-")
        await stats.monthly_stats(update, context, year=int(year_str), month=int(month_str))
    elif data == "stats:history":
        await stats.transaction_history(update, context)
    elif data.startswith("wallet:add:"):
        address = data.split(":", 2)[2]
        await wallet.add_wallet_from_address(update, context, address)
    elif data.startswith("wallet:delete:"):
        wallet_id = int(data.split(":")[2])
        await wallet.delete_wallet(update, context, wallet_id)
    elif data == "wallet:prompt_add":
        await wallet.prompt_add_wallet(update, context)
    elif data.startswith("wallet:detail:"):
        wallet_id = int(data.split(":")[2])
        await wallet.wallet_detail(update, context, wallet_id)
    elif data.startswith("alerts:toggle:"):
        wallet_id = int(data.split(":")[2])
        await alerts.toggle_wallet_alert(update, context, wallet_id, query.from_user.id)
    elif data == "price:set_target":
        await price_alert.prompt_set_target(update, context)
    elif data == "price:report_on":
        await price_alert.toggle_report(update, context)
    elif data == "admin:home":
        await admin.admin_panel(update, context)
    elif data == "admin:users":
        await respond(update, "유저 ID 또는 username을 `/finduser <id_or_username>` 명령으로 검색하세요\\.")
    elif data == "admin:payments":
        await admin.list_payments(update, context)
    elif data == "admin:settings":
        await admin.show_settings(update, context)
    elif data == "admin:halt":
        await admin.toggle_halt(update, context)
    elif data == "admin:broadcast":
        await admin.prompt_broadcast(update, context)
    elif data == "admin:scam":
        await admin.list_scam_tokens(update, context)
    elif data == "admin:scam_add":
        await admin.prompt_scam_add(update, context)
    elif data == "admin:scam_delete":
        await admin.prompt_scam_delete(update, context)
    elif data == "admin:scam_sync":
        await admin.sync_scam_tokens(update, context)
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
