from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from db import crud
from db.engine import get_session
from db.models import Transaction, TxDirection, WalletAddress
from utils.formatter import escape_md, format_amount


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
            target = update.message or update.callback_query.message
            await target.reply_text("등록된 지갑이 없습니다\\.", parse_mode="MarkdownV2")
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

    lines = [
        "📊 *오늘 통계*",
        f"_{escape_md(now.strftime('%Y-%m-%d'))} KST 기준_",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"📥 *총 입금*   \\+{escape_md(format_amount(deposit_total))} USDT _\\({len(deposits)}건\\)_",
        f"📤 *총 출금*   \\-{escape_md(format_amount(withdrawal_total))} USDT _\\({len(withdrawals)}건\\)_",
        "━━━━━━━━━━━━━━━━━━━━",
        f"💰 *순증감*    {escape_md(format_amount(deposit_total - withdrawal_total, sign=True))} USDT",
        "",
        f"📈 *최대 단건 입금*  \\+{escape_md(format_amount(max_deposit))} USDT",
        f"📉 *최소 단건 입금*  \\+{escape_md(format_amount(min_deposit))} USDT",
        f"📐 *입금 평균*       \\+{escape_md(format_amount(avg_deposit))} USDT",
        "",
        f"⚠️ _스캠 토큰 거래: {scam_count}건 감지됨_",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔵 이번 달 통계", callback_data="stats:monthly"), InlineKeyboardButton("🔵 거래내역 보기", callback_data="stats:history")],
            [InlineKeyboardButton("🏠 메인으로", callback_data="menu:home")],
        ]
    )
    target = update.message or update.callback_query.message
    await target.reply_text("\n".join(lines), parse_mode="MarkdownV2", reply_markup=keyboard)


async def monthly_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    now = datetime.now(timezone.utc)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    async with get_session() as session:
        wallet_ids = await _wallet_ids(session, telegram_id)
        if not wallet_ids:
            target = update.message or update.callback_query.message
            await target.reply_text("등록된 지갑이 없습니다\\.", parse_mode="MarkdownV2")
            return

        result = await session.execute(
            select(Transaction).where(
                Transaction.wallet_address_id.in_(wallet_ids),
                Transaction.block_timestamp >= start_of_month,
            )
        )
        txs = list(result.scalars().all())

    deposits = [t for t in txs if t.direction == TxDirection.in_]
    withdrawals = [t for t in txs if t.direction == TxDirection.out]
    deposit_total = sum(float(t.amount_usdt) for t in deposits)
    withdrawal_total = sum(float(t.amount_usdt) for t in withdrawals)
    max_tx = max(txs, key=lambda t: float(t.amount_usdt)) if txs else None

    lines = [
        f"📅 *{now.year}년 {now.month}월 통계*",
        "━━━━━━━━━━━━━━━━━━━━",
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
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("◀ 이전달", callback_data="stats:monthly:prev"), InlineKeyboardButton("다음달 ▶", callback_data="stats:monthly:next")],
            [InlineKeyboardButton("🏠 메인으로", callback_data="menu:home")],
        ]
    )
    target = update.message or update.callback_query.message
    await target.reply_text("\n".join(lines), parse_mode="MarkdownV2", reply_markup=keyboard)
