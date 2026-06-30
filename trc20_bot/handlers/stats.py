from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from db import crud
from db.engine import get_session
from db.models import Transaction, TxDirection, WalletAddress
from utils.formatter import escape_md, format_amount
from utils.respond import respond


async def _wallet_ids(session, telegram_id: int) -> list[int]:
    wallets = await crud.list_wallets(session, telegram_id)
    return [w.id for w in wallets]


async def today_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

    async with get_session() as session:
        wallet_ids = await _wallet_ids(session, telegram_id)
        if not wallet_ids:
            await respond(update, "📊 *오늘 통계*\n\n_등록된 지갑이 없습니다\\. 먼저 지갑을 등록해주세요\\._")
            return

        result = await session.execute(
            select(Transaction).where(
                Transaction.wallet_address_id.in_(wallet_ids),
                Transaction.block_timestamp >= start_of_day,
            )
        )
        txs = list(result.scalars().all())

    deposits = [t for t in txs if t.direction == TxDirection.in_]
    withdrawals = [t for t in txs if t.direction == TxDirection.out]
    deposit_total = sum(float(t.amount_usdt) for t in deposits)
    withdrawal_total = sum(float(t.amount_usdt) for t in withdrawals)
    scam_count = sum(1 for t in txs if t.is_scam_token)

    deposit_amounts = [float(t.amount_usdt) for t in deposits]
    max_deposit = max(deposit_amounts) if deposit_amounts else 0
    min_deposit = min(deposit_amounts) if deposit_amounts else 0
    avg_deposit = sum(deposit_amounts) / len(deposit_amounts) if deposit_amounts else 0

    net = deposit_total - withdrawal_total
    date_kst = now.strftime("%Y-%m-%d")
    lines = [
        "📊 오늘의 통계",
        "",
        f"💰 총 입금: {format_amount(deposit_total)} USDT",
        f"💸 총 출금: {format_amount(withdrawal_total)} USDT",
        f"📈 순이익: {format_amount(net)} USDT",
        "",
        f"📥 입금 횟수: {len(deposits)}회",
        f"📤 출금 횟수: {len(withdrawals)}회",
        f"🔄 총 거래: {len(txs)}건",
        "",
        f"📅 날짜: {date_kst}",
    ]
    if scam_count:
        lines.append(f"⚠️ 스캠 토큰 감지: {scam_count}건")

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("◀ 메인 메뉴", callback_data="menu:home")]]
    )
    await respond(update, "\n".join(lines), keyboard)


async def monthly_stats(update: Update, context: ContextTypes.DEFAULT_TYPE, year: int | None = None, month: int | None = None) -> None:
    telegram_id = update.effective_user.id
    now = datetime.now(timezone.utc)
    year = year or now.year
    month = month or now.month
    start_of_month = datetime(year, month, 1, tzinfo=timezone.utc)
    end_of_month = datetime(year + 1, 1, 1, tzinfo=timezone.utc) if month == 12 else datetime(year, month + 1, 1, tzinfo=timezone.utc)

    async with get_session() as session:
        wallet_ids = await _wallet_ids(session, telegram_id)
        if not wallet_ids:
            await respond(update, "📅 *월간 통계*\n\n_등록된 지갑이 없습니다\\. 먼저 지갑을 등록해주세요\\._")
            return

        result = await session.execute(
            select(Transaction).where(
                Transaction.wallet_address_id.in_(wallet_ids),
                Transaction.block_timestamp >= start_of_month,
                Transaction.block_timestamp < end_of_month,
            )
        )
        txs = list(result.scalars().all())

    deposits = [t for t in txs if t.direction == TxDirection.in_]
    withdrawals = [t for t in txs if t.direction == TxDirection.out]
    deposit_total = sum(float(t.amount_usdt) for t in deposits)
    withdrawal_total = sum(float(t.amount_usdt) for t in withdrawals)
    max_tx = max(txs, key=lambda t: float(t.amount_usdt)) if txs else None

    lines = [
        f"📅 *{year}년 {month}월 통계*",
        "━━━━━━━━━━━━━━━━━",
        "",
        f"📥 *총 입금*   \\+{escape_md(format_amount(deposit_total))} USDT _\\({len(deposits)}건\\)_",
        f"📤 *총 출금*   \\-{escape_md(format_amount(withdrawal_total))} USDT _\\({len(withdrawals)}건\\)_",
        f"💰 *순증감*    {escape_md(format_amount(deposit_total - withdrawal_total, sign=True))} USDT",
        "",
    ]
    if max_tx:
        lines.append(
            f"🏆 *최대 단건*  {escape_md(format_amount(float(max_tx.amount_usdt), sign=True))} USDT "
            f"_\\({escape_md(max_tx.block_timestamp.strftime('%m-%d'))}\\)_"
        )
    lines.append("━━━━━━━━━━━━━━━━━")

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("◀ 이전달", callback_data=f"stats:monthly:{prev_year}-{prev_month:02d}"),
                InlineKeyboardButton("다음달 ▶", callback_data=f"stats:monthly:{next_year}-{next_month:02d}"),
            ],
            [InlineKeyboardButton("🏠 메인으로", callback_data="menu:home")],
        ]
    )
    await respond(update, "\n".join(lines), keyboard)


async def transaction_history(update: Update, context: ContextTypes.DEFAULT_TYPE, limit: int = 15) -> None:
    telegram_id = update.effective_user.id

    async with get_session() as session:
        wallet_ids = await _wallet_ids(session, telegram_id)
        if not wallet_ids:
            await respond(update, "📋 *최근 거래내역*\n\n_등록된 지갑이 없습니다\\. 먼저 지갑을 등록해주세요\\._")
            return

        result = await session.execute(
            select(Transaction)
            .where(Transaction.wallet_address_id.in_(wallet_ids))
            .order_by(Transaction.block_timestamp.desc())
            .limit(limit)
        )
        txs = list(result.scalars().all())

    lines = ["📋 *최근 거래내역*", "━━━━━━━━━━━━━━━━━", ""]
    if not txs:
        lines.append("_아직 거래 내역이 없습니다\\._")
    for tx in txs:
        emoji = "🟢" if tx.direction == TxDirection.in_ else "🔴"
        sign = "\\+" if tx.direction == TxDirection.in_ else "\\-"
        lines.append(f"{emoji} *{sign}{escape_md(format_amount(float(tx.amount_usdt)))} USDT*")
        lines.append(f"   _{escape_md(tx.block_timestamp.strftime('%Y-%m-%d %H:%M'))}_")
        if tx.is_scam_token:
            lines.append("   ⚠️ *스캠 토큰 의심*")
        lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━")

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 메인으로", callback_data="menu:home")]])
    await respond(update, "\n".join(lines), keyboard)
