import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
from telegram.error import Forbidden

import runtime_state
from config import POLL_INTERVAL_SECONDS, PRICE_CHECK_INTERVAL_SECONDS, USDT_CONTRACT
from db import crud
from db.engine import get_session
from db.models import TxDirection
from services import scam_token, trongrid
from utils.formatter import deposit_alert, scam_warning_block, withdrawal_alert

logger = logging.getLogger(__name__)


async def poll_wallets(bot: Bot) -> None:
    if runtime_state.is_halted():
        return

    async with get_session() as session:
        wallets = await crud.list_active_wallets(session)

    for wallet in wallets:
        await _poll_one_wallet(bot, wallet)
        await asyncio.sleep(0.1)


async def _poll_one_wallet(bot: Bot, wallet) -> None:
    raw_txs = await trongrid.get_trc20_transactions(wallet.address, limit=20, contract_address=USDT_CONTRACT)
    if not raw_txs:
        return

    # First poll after registration: baseline silently so pre-existing history
    # isn't replayed as fresh deposit/withdrawal alerts.
    is_initial_baseline = wallet.last_tx_id is None

    async with get_session() as session:
        for tx in reversed(raw_txs):
            tx_id = tx.get("transaction_id", "")
            if not tx_id or tx_id == wallet.last_tx_id:
                continue

            token_info = tx.get("token_info", {})
            contract = token_info.get("address", USDT_CONTRACT)
            amount = int(tx.get("value", 0)) / 1_000_000
            from_address = tx.get("from", "")
            to_address = tx.get("to", "")
            direction = TxDirection.in_ if to_address == wallet.address else TxDirection.out
            block_time = datetime.fromtimestamp(tx.get("block_timestamp", 0) / 1000, tz=timezone.utc)

            is_scam = await scam_token.is_scam_token(session, contract, token_info.get("name"), token_info.get("symbol"))

            recorded = await crud.record_transaction(
                session,
                wallet,
                tx_id=tx_id,
                direction=direction,
                amount_usdt=amount,
                from_address=from_address,
                to_address=to_address,
                token_contract=contract,
                is_scam_token=is_scam,
                block_timestamp=block_time,
            )
            if recorded is None:
                continue

            if not is_initial_baseline:
                async with get_session() as user_session:
                    user = await crud.get_or_create_user(user_session, wallet.telegram_id, None)
                    if not user.alerts_enabled:
                        continue
                    if amount < float(user.min_alert_amount):
                        continue
                await _send_alert(bot, wallet, direction, amount, from_address, to_address, tx_id, block_time, is_scam, token_info)


async def _send_alert(bot, wallet, direction, amount, from_address, to_address, tx_id, block_time, is_scam, token_info) -> None:
    label = wallet.label or "지갑"
    try:
        if direction == TxDirection.in_:
            text = deposit_alert(label, wallet.address, amount, from_address, tx_id, block_time)
        else:
            text = withdrawal_alert(label, wallet.address, amount, to_address, 0.0, tx_id, block_time)

        if is_scam:
            text += "\n\n" + scam_warning_block(token_info.get("name", "Unknown"), token_info.get("address", ""))

        await bot.send_message(chat_id=wallet.telegram_id, text=text, parse_mode="MarkdownV2")
    except Forbidden:
        async with get_session() as session:
            await crud.deactivate_wallet(session, wallet.id)


async def check_plan_expirations(bot: Bot) -> None:
    async with get_session() as session:
        expiring = await crud.list_expiring_pro_users(session, within_days=3)
        for user in expiring:
            try:
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text="👑 Pro 플랜이 3일 후 만료됩니다\\. 갱신해주세요\\!",
                    parse_mode="MarkdownV2",
                )
            except Forbidden:
                pass

        expired = await crud.list_expired_pro_users(session)
        for user in expired:
            await crud.downgrade_user(session, user)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    from handlers.price_alert import check_price_targets, send_hourly_reports

    scheduler = AsyncIOScheduler()
    scheduler.add_job(poll_wallets, "interval", seconds=POLL_INTERVAL_SECONDS, args=[bot])
    scheduler.add_job(check_plan_expirations, "cron", hour=0, minute=0, args=[bot])
    scheduler.add_job(check_price_targets, "interval", seconds=PRICE_CHECK_INTERVAL_SECONDS, args=[bot])
    scheduler.add_job(send_hourly_reports, "interval", hours=1, args=[bot])
    return scheduler
