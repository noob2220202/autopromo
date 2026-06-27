from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from db import crud
from db.engine import get_session
from utils.formatter import escape_md


async def toggle_wallet_alert(update: Update, context: ContextTypes.DEFAULT_TYPE, wallet_id: int, telegram_id: int) -> None:
    async with get_session() as session:
        wallets = await crud.list_wallets(session, telegram_id)
        wallet = next((w for w in wallets if w.id == wallet_id), None)
        if wallet is None:
            target = update.message or update.callback_query.message
            await target.reply_text("❌ 지갑을 찾을 수 없습니다\\.", parse_mode="MarkdownV2")
            return
        wallet.is_active = not wallet.is_active
        await session.commit()

    await show_alerts_menu(update, context)


async def show_alerts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    async with get_session() as session:
        wallets = await crud.list_wallets(session, telegram_id)

    target = update.message or update.callback_query.message
    if not wallets:
        await target.reply_text(
            "🔔 *알림 설정*\n━━━━━━━━━━━━━━━━━\n\n등록된 지갑이 없습니다\\. 먼저 지갑을 등록해주세요\\.",
            parse_mode="MarkdownV2",
        )
        return

    lines = ["🔔 *알림 설정*", "━━━━━━━━━━━━━━━━━", ""]
    buttons = []
    for idx, wallet in enumerate(wallets, start=1):
        label = wallet.label or "지갑"
        state = "🟢 활성" if wallet.is_active else "🔴 비활성"
        lines.append(f"{idx}\\. 🏷️ _{escape_md(label)}_ \\(`{wallet.address}`\\) — {state}")
        toggle_label = "🔴 알림 끄기" if wallet.is_active else "🟢 알림 켜기"
        buttons.append([InlineKeyboardButton(f"{idx}번 {toggle_label}", callback_data=f"alerts:toggle:{wallet.id}")])
    lines.append("━━━━━━━━━━━━━━━━━")
    buttons.append([InlineKeyboardButton("🏠 메인으로", callback_data="menu:home")])

    await target.reply_text("\n".join(lines), parse_mode="MarkdownV2", reply_markup=InlineKeyboardMarkup(buttons))
