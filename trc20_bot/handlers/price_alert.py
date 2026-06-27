from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from db import crud
from db.engine import get_session
from services import price
from utils.formatter import escape_md


async def show_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await price.get_usdt_price()
    if data is None:
        target = update.message or update.callback_query.message
        await target.reply_text("❌ 시세 조회에 실패했습니다\\.", parse_mode="MarkdownV2")
        return

    telegram_id = update.effective_user.id
    async with get_session() as session:
        user = await crud.get_or_create_user(session, telegram_id, update.effective_user.username)
        alert_state = "🟢 활성" if user.price_alert_on else "🔴 비활성"

    change = data["usd_24h_change"]
    change_str = f"+{change:.2f}" if change >= 0 else f"{change:.2f}"
    usd_str = f"{data['usd']:.3f}"
    krw_str = f"{data['krw']:,.1f}"

    lines = [
        "📈 *USDT 현재 시세*",
        "━━━━━━━━━━━━━━━━━",
        "",
        f"💵 USD  *${escape_md(usd_str)}*",
        f"🇰🇷 KRW  *₩{escape_md(krw_str)}*",
        "",
        f"📊 24h 변동: _{escape_md(change_str)}%_",
        "",
        "━━━━━━━━━━━━━━━━━",
        f"🔔 시세 알림: *{alert_state}*",
    ]

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🟢 목표가 알림 설정", callback_data="price:set_target"), InlineKeyboardButton("🔵 1시간 리포트 ON", callback_data="price:report_on")],
            [InlineKeyboardButton("🏠 메인으로", callback_data="menu:home")],
        ]
    )
    target = update.message or update.callback_query.message
    await target.reply_text("\n".join(lines), parse_mode="MarkdownV2", reply_markup=keyboard)


async def prompt_set_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["awaiting"] = "price_target"
    target = update.message or update.callback_query.message
    await target.reply_text("🟢 알림을 받을 목표가\\(USD\\)를 숫자로 입력해주세요\\.", parse_mode="MarkdownV2")


async def toggle_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    async with get_session() as session:
        user = await crud.get_or_create_user(session, telegram_id, update.effective_user.username)
        user.price_report_on = not user.price_report_on
        new_state = user.price_report_on
        await session.commit()

    target = update.message or update.callback_query.message
    state_str = "켜졌습니다" if new_state else "꺼졌습니다"
    await target.reply_text(f"🔵 1시간 리포트가 {state_str}\\.", parse_mode="MarkdownV2")


async def send_hourly_reports(bot) -> None:
    data = await price.get_usdt_price()
    if data is None:
        return

    from sqlalchemy import select

    from db.models import User

    change = data["usd_24h_change"]
    change_str = f"+{change:.2f}" if change >= 0 else f"{change:.2f}"
    usd_str = f"{data['usd']:.3f}"
    krw_str = f"{data['krw']:,.1f}"
    text = (
        "📈 *1시간 정기 리포트*\n━━━━━━━━━━━━━━━━━\n\n"
        f"💵 USD  *${escape_md(usd_str)}*\n"
        f"🇰🇷 KRW  *₩{escape_md(krw_str)}*\n"
        f"📊 24h 변동: _{escape_md(change_str)}%_"
    )

    from telegram.error import Forbidden

    async with get_session() as session:
        result = await session.execute(select(User).where(User.price_report_on.is_(True)))
        for user in result.scalars().all():
            try:
                await bot.send_message(chat_id=user.telegram_id, text=text, parse_mode="MarkdownV2")
            except Forbidden:
                pass


async def set_price_target(update: Update, context: ContextTypes.DEFAULT_TYPE, target_price: float) -> None:
    telegram_id = update.effective_user.id
    async with get_session() as session:
        user = await crud.get_or_create_user(session, telegram_id, update.effective_user.username)
        user.price_alert_on = True
        user.price_alert_target = target_price
        await session.commit()

    message_target = update.message or update.callback_query.message
    await message_target.reply_text(
        f"🟢 목표가 알림이 설정되었습니다: ${escape_md(str(target_price))}", parse_mode="MarkdownV2"
    )


async def check_price_targets(bot) -> None:
    data = await price.get_usdt_price()
    if data is None:
        return

    from sqlalchemy import select

    from db.models import User

    async with get_session() as session:
        result = await session.execute(select(User).where(User.price_alert_on.is_(True)))
        for user in result.scalars().all():
            if user.price_alert_target and data["usd"] >= float(user.price_alert_target):
                target_str = escape_md(str(user.price_alert_target))
                current_str = escape_md(str(data["usd"]))
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=f"🔔 USDT가 목표가 ${target_str}에 도달했습니다\\. 현재가: ${current_str}",
                    parse_mode="MarkdownV2",
                )
                user.price_alert_on = False
        await session.commit()
