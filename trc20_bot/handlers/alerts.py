from telegram import Update
from telegram.ext import ContextTypes

from db import crud
from db.engine import get_session


async def toggle_wallet_alert(update: Update, context: ContextTypes.DEFAULT_TYPE, wallet_id: int, telegram_id: int) -> None:
    async with get_session() as session:
        wallets = await crud.list_wallets(session, telegram_id)
        wallet = next((w for w in wallets if w.id == wallet_id), None)
        if wallet is None:
            return
        wallet.is_active = not wallet.is_active
        await session.commit()
        new_state = "🟢 활성" if wallet.is_active else "🔴 비활성"

    target = update.message or update.callback_query.message
    await target.reply_text(f"알림 상태가 변경되었습니다: {new_state}", parse_mode="MarkdownV2")
