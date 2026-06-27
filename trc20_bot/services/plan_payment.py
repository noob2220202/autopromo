from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from config import OWNER_WALLET_ADDRESS, PRO_PLAN_DAYS, PRO_PLAN_USDT_PRICE, USDT_CONTRACT
from db import crud
from services import trongrid


class PaymentVerificationError(Exception):
    pass


async def verify_and_confirm(session: AsyncSession, tx_id: str, telegram_id: int) -> dict:
    existing = await crud.get_payment_by_tx(session, tx_id)
    if existing is not None:
        raise PaymentVerificationError("이미 사용된 TX 해시입니다.")

    tx = await trongrid.get_transaction(tx_id)
    if tx is None:
        raise PaymentVerificationError("TX를 찾을 수 없습니다.")

    contract = tx.get("token_info", {}).get("address") or tx.get("contract_address")
    to_address = tx.get("to_address") or tx.get("to")
    raw_amount = tx.get("amount") or tx.get("value") or 0
    amount = float(raw_amount) / 1_000_000
    timestamp_ms = tx.get("block_timestamp") or tx.get("raw_data", {}).get("timestamp", 0)
    block_time = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

    if contract != USDT_CONTRACT:
        raise PaymentVerificationError("USDT(TRC20) 거래가 아닙니다.")
    if to_address != OWNER_WALLET_ADDRESS:
        raise PaymentVerificationError("받는 주소가 오너 지갑과 일치하지 않습니다.")
    if amount < PRO_PLAN_USDT_PRICE:
        raise PaymentVerificationError(f"금액이 {PRO_PLAN_USDT_PRICE} USDT 미만입니다.")
    if datetime.now(timezone.utc) - block_time > timedelta(hours=1):
        raise PaymentVerificationError("TX 발생 후 1시간이 지났습니다.")

    payment = await crud.create_payment(session, telegram_id, tx_id, amount)
    user = await crud.confirm_payment(session, payment, pro_plan_days=PRO_PLAN_DAYS)
    return {"user": user, "tx_id": tx_id, "amount": amount}
