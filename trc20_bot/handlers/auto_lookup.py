from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import USDT_CONTRACT
from db.engine import get_session
from services import scam_token, trongrid
from services.plan_payment import PaymentVerificationError, verify_and_confirm
from utils.formatter import escape_md, wallet_summary
from utils.validators import is_tron_address, is_tx_hash


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()

    if is_tx_hash(text):
        await _handle_tx_hash(update, context, text)
        return

    if is_tron_address(text):
        await _handle_address(update, context, text)
        return


async def _handle_address(update: Update, context: ContextTypes.DEFAULT_TYPE, address: str) -> None:
    balance = await trongrid.get_balance(address)
    raw_txs = await trongrid.get_trc20_transactions(address, limit=10, contract_address=USDT_CONTRACT)

    txs = []
    async with get_session() as session:
        for tx in raw_txs:
            contract = tx.get("token_info", {}).get("address", USDT_CONTRACT)
            is_scam = await scam_token.is_scam_token(
                session,
                contract,
                tx.get("token_info", {}).get("name"),
                tx.get("token_info", {}).get("symbol"),
            )
            direction = "in" if tx.get("to") == address else "out"
            txs.append(
                {
                    "tx_id": tx.get("transaction_id", ""),
                    "direction": direction,
                    "amount_usdt": int(tx.get("value", 0)) / 1_000_000,
                    "from_address": tx.get("from", ""),
                    "to_address": tx.get("to", ""),
                    "block_timestamp": datetime.fromtimestamp(tx.get("block_timestamp", 0) / 1000, tz=timezone.utc),
                    "is_scam_token": is_scam,
                }
            )

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔵 더 보기", callback_data=f"lookup:more:{address}"), InlineKeyboardButton("🟢 이 주소 등록", callback_data=f"wallet:add:{address}")],
            [InlineKeyboardButton("🔗 TronScan에서 보기", url=f"https://tronscan.org/#/address/{address}")],
        ]
    )
    await update.message.reply_text(
        wallet_summary(address, balance, txs), parse_mode="MarkdownV2", reply_markup=keyboard
    )


async def _handle_tx_hash(update: Update, context: ContextTypes.DEFAULT_TYPE, tx_id: str) -> None:
    telegram_id = update.effective_user.id
    async with get_session() as session:
        try:
            result = await verify_and_confirm(session, tx_id, telegram_id)
        except PaymentVerificationError as exc:
            await update.message.reply_text(
                f"> ❌ *결제 확인 실패*\n>\n> {escape_md(str(exc))}",
                parse_mode="MarkdownV2",
            )
            return

    await update.message.reply_text(
        "✅ *Pro 플랜 활성화 완료\\!*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎉 업그레이드를 축하드립니다\\!\n\n"
        f"👑 *현재 플랜:* Pro\n"
        f"📍 *주소 한도:* 최대 5개\n"
        f"🔗 확인된 TX: `{result['tx_id']}`",
        parse_mode="MarkdownV2",
    )
