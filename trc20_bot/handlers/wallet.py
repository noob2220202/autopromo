from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import FREE_PLAN_WALLET_LIMIT, PRO_PLAN_WALLET_LIMIT
from db import crud
from db.engine import get_session
from db.models import PlanType
from handlers.start import MAIN_KEYBOARD, NO_WALLET_GUIDE
from services import trongrid
from utils.formatter import escape_md, format_amount, format_datetime_kst, short_address, to_kst
from utils.respond import respond
from utils.validators import is_tron_address


def _limit_for_plan(plan: PlanType) -> int:
    return PRO_PLAN_WALLET_LIMIT if plan == PlanType.pro else FREE_PLAN_WALLET_LIMIT


WALLET_GUIDE_TEXT = (
    "📒 지갑 등록 및 변경 방법\n"
    "USDT 지갑만 등록 가능합니다\n\n"
    "━━━━━━━━━━━━━━━━━\n\n"
    "1. 지갑 주소를 /p [지갑주소] 형식으로 입력해주세요\n"
    "   예) /p TRzMKdv6Jw5p25h2EFcum9m6UdukAQcDhP\n\n"
    "2. 무료 사용자는 1개, 프리미엄 사용자는 5개까지 등록 가능\n\n"
    "3. 지갑 삭제는 /d [지갑주소] 형식으로 입력\n"
    "   예) /d TRzMKdv6Jw5p25h2EFcum9m6UdukAQcDhP\n\n"
    "━━━━━━━━━━━━━━━━━\n\n"
    "💡 중요:\n"
    "- Tron(TRC20) 주소만 지원\n"
    "- 주소는 'T'로 시작하며 34자\n"
    "- 등록 시점부터 입출금 모니터링 시작\n"
    "- 이전 거래 내역은 알림 제외"
)


async def show_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    async with get_session() as session:
        wallets = await crud.list_wallets(session, telegram_id)

    if not wallets:
        await respond(
            update,
            NO_WALLET_GUIDE,
            InlineKeyboardMarkup([[InlineKeyboardButton("◀ 메인 메뉴", callback_data="menu:home")]]),
        )
        return

    buttons = []
    for idx, wallet in enumerate(wallets, start=1):
        truncated = short_address(wallet.address, 6, 4)
        buttons.append([InlineKeyboardButton(f"{idx}. {truncated}", callback_data=f"wallet:detail:{wallet.id}")])
    buttons.append([InlineKeyboardButton("◀ 메인 메뉴", callback_data="menu:home")])

    await respond(
        update,
        "📋 내 지갑 목록\n\n지갑을 선택하여 상세 정보를 확인하세요:",
        InlineKeyboardMarkup(buttons),
    )


async def wallet_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, wallet_id: int) -> None:
    telegram_id = update.effective_user.id
    async with get_session() as session:
        wallets = await crud.list_wallets(session, telegram_id)
    wallet = next((w for w in wallets if w.id == wallet_id), None)

    if wallet is None:
        await respond(update, "❌ 지갑을 찾을 수 없습니다.")
        return

    from db.models import Transaction, TxDirection
    from sqlalchemy import select
    from db.engine import get_session as gs

    balance = await trongrid.get_balance(wallet.address)
    registered_kst = format_datetime_kst(wallet.created_at).replace(" KST", " KST")

    async with gs() as session:
        result = await session.execute(
            select(Transaction)
            .where(Transaction.wallet_address_id == wallet.id)
            .order_by(Transaction.block_timestamp.desc())
            .limit(5)
        )
        recent_txs = list(result.scalars().all())

    tx_lines = []
    if not recent_txs:
        tx_lines.append("거래 내역 없음")
    else:
        for tx in recent_txs:
            emoji = "🟢" if tx.direction == TxDirection.in_ else "🔴"
            sign = "+" if tx.direction == TxDirection.in_ else "-"
            tx_lines.append(f"{emoji} {sign}{format_amount(float(tx.amount_usdt))} USDT")
            tx_lines.append(f"   {format_datetime_kst(tx.block_timestamp)}")

    text = (
        f"📍 지갑 상세 정보\n\n"
        f"주소: {wallet.address}\n\n"
        f"💰 현재 USDT 잔액: {format_amount(balance)}\n"
        f"📅 등록일: {registered_kst}\n\n"
        "━━━━━━━━━━━━━━━━━\n\n"
        f"📊 최근 거래 내역 (최근 5건)\n\n"
        + "\n".join(tx_lines)
    )

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🗑️ 이 지갑 삭제", callback_data=f"wallet:delete:{wallet.id}")],
            [InlineKeyboardButton("◀ 지갑 목록", callback_data="menu:wallet")],
        ]
    )
    await respond(update, text, keyboard)


async def add_wallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            WALLET_GUIDE_TEXT,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀ 메인 메뉴", callback_data="menu:home")]]),
        )
        return

    address = context.args[0].strip()
    telegram_id = update.effective_user.id

    if not is_tron_address(address):
        await update.message.reply_text(
            "❌ 올바른 트론(TRC20) 주소가 아닙니다.\n주소는 'T'로 시작하며 34자입니다."
        )
        return

    async with get_session() as session:
        user = await crud.get_or_create_user(session, telegram_id, update.effective_user.username)
        plan = await crud.get_active_plan(user)
        wallets = await crud.list_wallets(session, telegram_id)
        limit = _limit_for_plan(plan)

        if len(wallets) >= limit:
            await update.message.reply_text(
                f"❌ 지갑 등록 한도 초과!\n\n"
                f"무료 플랜은 최대 {FREE_PLAN_WALLET_LIMIT}개까지 등록 가능합니다.\n"
                f"프리미엄으로 업그레이드하면 최대 {PRO_PLAN_WALLET_LIMIT}개까지 등록 가능합니다.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👑 프리미엄 구매", callback_data="menu:plan")]]),
            )
            return

        if any(w.address == address for w in wallets):
            await update.message.reply_text("이미 등록된 지갑 주소입니다.")
            return

        await crud.add_wallet(session, telegram_id, address, label=None)

    balance = await trongrid.get_balance(address)
    await update.message.reply_text(
        f"✅✅ 지갑이 등록되었습니다!\n\n"
        f"💰 현재 USDT 잔액: {format_amount(balance)}\n"
        f"📍 지갑: {address}\n\n"
        f"🔔 지금부터 발생하는 USDT 입출금만 모니터링합니다!",
        reply_markup=MAIN_KEYBOARD,
    )


async def delete_wallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "사용법: /d [지갑주소]\n예) /d TRzMKdv6Jw5p25h2EFcum9m6UdukAQcDhP"
        )
        return

    address = context.args[0].strip()
    telegram_id = update.effective_user.id

    async with get_session() as session:
        wallets = await crud.list_wallets(session, telegram_id)
        wallet = next((w for w in wallets if w.address == address), None)
        if wallet is None:
            await update.message.reply_text("❌ 등록된 지갑에서 해당 주소를 찾을 수 없습니다.")
            return
        await crud.delete_wallet(session, wallet.id, telegram_id)

    await update.message.reply_text(
        f"🗑️ 지갑이 삭제되었습니다.\n{address}",
        reply_markup=MAIN_KEYBOARD,
    )


async def delete_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE, wallet_id: int) -> None:
    telegram_id = update.effective_user.id
    async with get_session() as session:
        wallets = await crud.list_wallets(session, telegram_id)
        wallet = next((w for w in wallets if w.id == wallet_id), None)
        address = wallet.address if wallet else ""
        deleted = await crud.delete_wallet(session, wallet_id, telegram_id)

    if deleted:
        await respond(
            update,
            f"🗑️ 지갑이 삭제되었습니다.\n{address}",
            InlineKeyboardMarkup([[InlineKeyboardButton("◀ 지갑 목록", callback_data="menu:wallet")]]),
        )
    else:
        await respond(update, "❌ 삭제할 지갑을 찾을 수 없습니다.")


async def show_add_wallet_guide(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await respond(
        update,
        WALLET_GUIDE_TEXT,
        InlineKeyboardMarkup([[InlineKeyboardButton("◀ 메인 메뉴", callback_data="menu:home")]]),
    )


async def add_wallet_from_address(update: Update, context: ContextTypes.DEFAULT_TYPE, address: str) -> None:
    """Called from auto_lookup when address typed in chat — just show info, no auto-register."""
    pass
