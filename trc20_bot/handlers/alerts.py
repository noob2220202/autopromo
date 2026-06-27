from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from db import crud
from db.engine import get_session
from utils.formatter import escape_md
from utils.respond import respond


async def toggle_wallet_alert(update: Update, context: ContextTypes.DEFAULT_TYPE, wallet_id: int, telegram_id: int) -> None:
    async with get_session() as session:
        wallets = await crud.list_wallets(session, telegram_id)
        wallet = next((w for w in wallets if w.id == wallet_id), None)
        if wallet is None:
            await respond(update, "❌ 지갑을 찾을 수 없습니다\\.")
            return
        wallet.is_active = not wallet.is_active
        await session.commit()

    await show_alerts_menu(update, context)


async def show_alerts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    async with get_session() as session:
        wallets = await crud.list_wallets(session, telegram_id)

    if not wallets:
        await respond(
            update,
            "🔔 *알림 설정*\n━━━━━━━━━━━━━━━━━\n\n_등록된 지갑이 없습니다\\. 먼저 지갑을 등록해주세요\\._",
        )
        return

    lines = ["🔔 *알림 설정*", "━━━━━━━━━━━━━━━━━", "", "_지갑별로 입출금 알림을 켜고 끌 수 있어요\\._", ""]
    buttons = []
    for idx, wallet in enumerate(wallets, start=1):
        label = wallet.label or "지갑"
        state = "🟢 활성" if wallet.is_active else "🔴 비활성"
        lines.append(f"{idx}\\. 🏷️ *{escape_md(label)}* \\(`{wallet.address}`\\) — {state}")
        toggle_label = "🔴 알림 끄기" if wallet.is_active else "🟢 알림 켜기"
        buttons.append([InlineKeyboardButton(f"{idx}번 {toggle_label}", callback_data=f"alerts:toggle:{wallet.id}")])
    lines.append("━━━━━━━━━━━━━━━━━")
    buttons.append([InlineKeyboardButton("🏠 메인으로", callback_data="menu:home")])

    await respond(update, "\n".join(lines), InlineKeyboardMarkup(buttons))
