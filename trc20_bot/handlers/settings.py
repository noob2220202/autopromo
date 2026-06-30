from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from db import crud
from db.engine import get_session
from utils.formatter import format_amount
from utils.respond import respond


async def show_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    async with get_session() as session:
        user = await crud.get_or_create_user(session, telegram_id, update.effective_user.username)
        alerts_on = user.alerts_enabled
        min_amount = float(user.min_alert_amount)

    toggle_label = "🔔 알림 끄기" if alerts_on else "🔔 알림 켜기"
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(toggle_label, callback_data="settings:toggle")],
            [InlineKeyboardButton(f"💵 최소 금액 설정 (현재: {format_amount(min_amount)} USDT)", callback_data="settings:set_min")],
            [InlineKeyboardButton("◀ 메인 메뉴", callback_data="menu:home")],
        ]
    )
    await respond(
        update,
        "⚙️ 설정 메뉴\n\n알림 설정과 최소 금액을 조정할 수 있습니다.",
        keyboard,
    )


async def toggle_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    async with get_session() as session:
        user = await crud.get_or_create_user(session, telegram_id, update.effective_user.username)
        user.alerts_enabled = not user.alerts_enabled
        new_state = user.alerts_enabled
        await session.commit()

    state_str = "켜졌습니다 🔔" if new_state else "꺼졌습니다 🔕"
    await show_settings_menu(update, context)


async def prompt_set_min(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["awaiting"] = "settings_min"
    await respond(
        update,
        "💵 최소 알림 금액 설정\n\n"
        "이 금액 이상의 입출금만 알림을 받습니다.\n"
        "0으로 설정하면 모든 거래를 알립니다.\n\n"
        "금액(USDT)을 숫자로 입력해주세요.\n예) 10",
        InlineKeyboardMarkup([[InlineKeyboardButton("◀ 취소", callback_data="menu:settings")]]),
    )


async def set_min_amount(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: float) -> None:
    telegram_id = update.effective_user.id
    async with get_session() as session:
        user = await crud.get_or_create_user(session, telegram_id, update.effective_user.username)
        user.min_alert_amount = amount
        await session.commit()

    await update.message.reply_text(
        f"✅ 최소 알림 금액이 {format_amount(amount)} USDT로 설정되었습니다.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ 설정으로 돌아가기", callback_data="menu:settings")]]),
    )
