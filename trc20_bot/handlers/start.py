from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import ADMIN_IDS, BOT_DISPLAY_NAME, SUPPORT_USERNAME
from db import crud
from db.engine import get_session

MAIN_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("📊 오늘 통계", callback_data="menu:stats"), InlineKeyboardButton("📈 월간 통계", callback_data="menu:monthly")],
        [InlineKeyboardButton("➕ 지갑 추가", callback_data="menu:add_wallet"), InlineKeyboardButton("📋 내 지갑 목록", callback_data="menu:wallet")],
        [InlineKeyboardButton("⚙️ 설정", callback_data="menu:settings"), InlineKeyboardButton("📞 고객센터", callback_data="menu:customer")],
        [InlineKeyboardButton("👑 프리미엄 구매", callback_data="menu:plan"), InlineKeyboardButton("🤝 제휴업체 목록", callback_data="menu:affiliate")],
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


def main_menu_text() -> str:
    return (
        f"👑 {BOT_DISPLAY_NAME} 👑\n\n"
        "\"로얄클럽만의 USDT 입금알림 전용 봇\"\n"
        "지금 채널을 구독하시면 무료로\n"
        "이용하실수있습니다\n\n"
        "보다 편리한 자산 관리 알림봇으로,\n"
        "입출금 관리 · 화이트모니터링 · 금액알림 설정까지\n"
        "단 하나의 봇으로 해결합니다\n\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        "기능 설명\n\n"
        "1. 컨트랙트일치여부로 가짜 테더 완벽 차단 알림\n"
        "스마트컨트랙트와의 정밀 대조를 통해\n"
        "위조된 USDT를 자동 식별 및 차단합니다.\n\n"
        "2. 사용자 맞춤 편의성의 완벽한 조화\n"
        "직관적인 인터페이스로 안전하고 효율적인\n"
        "자산 관리 환경을 지원합니다.\n\n"
        "3. 프리미엄 구매시 기존지갑 1개 연결 → 5개 연결가능\n"
        "알림이 올때마다 광고노출제거\n"
        "광고가 보기싫다면 프리미엄 구독!\n\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        f"메인광고 및 이용문의: {SUPPORT_USERNAME}\n\n"
        "아래 버튼을 눌러 기능을 사용하세요 👇"
    )


NO_WALLET_GUIDE = (
    "📋 등록된 지갑이 없습니다\n\n"
    "/p [지갑주소] 명령어로 지갑을 추가하세요.\n\n"
    "예) /p TRzMKdv6Jw5p25h2EFcum9m6UdukAQcDhP"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    username = update.effective_user.username

    async with get_session() as session:
        await crud.get_or_create_user(session, telegram_id, username)
        wallets = await crud.list_wallets(session, telegram_id)

    if telegram_id in ADMIN_IDS:
        await update.message.reply_text(
            "👑 *관리자 패널*\n━━━━━━━━━━━━━━━━━\n_아래에서 관리 기능을 선택하세요\\._",
            parse_mode="MarkdownV2",
            reply_markup=ADMIN_MENU_KEYBOARD,
        )
        return

    if not wallets:
        await update.message.reply_text(
            NO_WALLET_GUIDE,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀ 메인 메뉴", callback_data="menu:home")]]),
        )

    await update.message.reply_text(main_menu_text(), reply_markup=MAIN_KEYBOARD)
