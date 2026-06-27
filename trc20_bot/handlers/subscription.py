from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import OWNER_WALLET_ADDRESS, PRO_PLAN_USDT_PRICE
from utils.formatter import escape_md


async def show_plan_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "💳 *Pro 플랜 안내*\n━━━━━━━━━━━━━━━━━\n\n"
        f"*등록된 지갑 주소*에서 아래 주소로 정확히 *{escape_md(str(PRO_PLAN_USDT_PRICE))} USDT\\(TRC20\\)*를 보내고,\n"
        "거래 TX 해시를 이 채팅에 붙여넣어주세요\\.\n\n"
        f"오너 주소: `{OWNER_WALLET_ADDRESS}`\n\n"
        "> ⚠️ 보낸 지갑 주소가 봇에 *등록된 주소*와 다르거나,\n"
        "> 금액이 정확히 일치하지 않으면 승인되지 않습니다\\."
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 메인으로", callback_data="menu:home")]])
    target = update.message or update.callback_query.message
    await target.reply_text(text, parse_mode="MarkdownV2", reply_markup=keyboard)
