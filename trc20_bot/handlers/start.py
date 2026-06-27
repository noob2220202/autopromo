from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import ADMIN_IDS
from db.engine import get_session
from db import crud

USER_MENU_TEXT = (
    "🤖 *TRC20 USDT 봇에 오신 걸 환영합니다\\!*\n\n"
    "주소를 채팅창에 바로 입력하면 즉시 조회할 수 있어요\\.\n"
    "아래 메뉴에서 원하는 기능을 선택하세요\\."
)

USER_MENU_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("💼 내 지갑", callback_data="menu:wallet"), InlineKeyboardButton("📊 통계", callback_data="menu:stats")],
        [InlineKeyboardButton("🔔 알림 설정", callback_data="menu:alerts"), InlineKeyboardButton("📈 시세", callback_data="menu:price")],
        [InlineKeyboardButton("💳 플랜 관리", callback_data="menu:plan"), InlineKeyboardButton("❓ 도움말", callback_data="menu:help")],
    ]
)

ADMIN_MENU_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("👥 유저 관리", callback_data="admin:users"), InlineKeyboardButton("💳 결제 내역", callback_data="admin:payments")],
        [InlineKeyboardButton("🚨 스캠 토큰 관리", callback_data="admin:scam"), InlineKeyboardButton("📢 공지 발송", callback_data="admin:broadcast")],
        [InlineKeyboardButton("📊 전체 통계", callback_data="admin:stats"), InlineKeyboardButton("⚙️ 봇 설정", callback_data="admin:settings")],
        [InlineKeyboardButton("🔴 긴급 봇 정지", callback_data="admin:halt")],
    ]
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    username = update.effective_user.username

    async with get_session() as session:
        await crud.get_or_create_user(session, telegram_id, username)

    if telegram_id in ADMIN_IDS:
        await update.message.reply_text(
            "👑 *관리자 패널*\n━━━━━━━━━━━━━━━━━━━━",
            parse_mode="MarkdownV2",
            reply_markup=ADMIN_MENU_KEYBOARD,
        )
        return

    await update.message.reply_text(USER_MENU_TEXT, parse_mode="MarkdownV2", reply_markup=USER_MENU_KEYBOARD)
