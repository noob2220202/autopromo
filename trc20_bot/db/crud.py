from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    PlanPayment,
    PlanPaymentStatus,
    PlanType,
    ScamToken,
    Transaction,
    TxDirection,
    User,
    WalletAddress,
)


async def get_or_create_user(session: AsyncSession, telegram_id: int, username: str | None) -> User:
    user = await session.get(User, telegram_id)
    if user is None:
        user = User(telegram_id=telegram_id, username=username)
        session.add(user)
        await session.commit()
    elif username and user.username != username:
        user.username = username
        await session.commit()
    return user


async def get_active_plan(user: User) -> PlanType:
    if user.plan == PlanType.pro and user.plan_expires_at and user.plan_expires_at > datetime.now(timezone.utc):
        return PlanType.pro
    return PlanType.free


async def list_wallets(session: AsyncSession, telegram_id: int) -> list[WalletAddress]:
    result = await session.execute(
        select(WalletAddress).where(WalletAddress.telegram_id == telegram_id).order_by(WalletAddress.id)
    )
    return list(result.scalars().all())


async def list_active_wallets(session: AsyncSession) -> list[WalletAddress]:
    result = await session.execute(select(WalletAddress).where(WalletAddress.is_active.is_(True)))
    return list(result.scalars().all())


async def add_wallet(session: AsyncSession, telegram_id: int, address: str, label: str | None) -> WalletAddress:
    wallet = WalletAddress(telegram_id=telegram_id, address=address, label=label)
    session.add(wallet)
    await session.commit()
    return wallet


async def delete_wallet(session: AsyncSession, wallet_id: int, telegram_id: int) -> bool:
    wallet = await session.get(WalletAddress, wallet_id)
    if wallet is None or wallet.telegram_id != telegram_id:
        return False
    await session.delete(wallet)
    await session.commit()
    return True


async def deactivate_wallet(session: AsyncSession, wallet_id: int) -> None:
    wallet = await session.get(WalletAddress, wallet_id)
    if wallet:
        wallet.is_active = False
        await session.commit()


async def record_transaction(
    session: AsyncSession,
    wallet: WalletAddress,
    tx_id: str,
    direction: TxDirection,
    amount_usdt: float,
    from_address: str,
    to_address: str,
    token_contract: str,
    is_scam_token: bool,
    block_timestamp: datetime,
    fee_trx: float = 0,
) -> Transaction | None:
    existing = await session.execute(select(Transaction).where(Transaction.tx_id == tx_id))
    if existing.scalar_one_or_none() is not None:
        return None
    tx = Transaction(
        wallet_address_id=wallet.id,
        tx_id=tx_id,
        direction=direction,
        amount_usdt=amount_usdt,
        from_address=from_address,
        to_address=to_address,
        token_contract=token_contract,
        is_scam_token=is_scam_token,
        block_timestamp=block_timestamp,
        fee_trx=fee_trx,
    )
    session.add(tx)
    wallet.last_tx_id = tx_id
    await session.commit()
    return tx


async def get_scam_token(session: AsyncSession, contract_address: str) -> ScamToken | None:
    result = await session.execute(select(ScamToken).where(ScamToken.contract_address == contract_address))
    return result.scalar_one_or_none()


async def cache_scam_token(
    session: AsyncSession,
    contract_address: str,
    is_scam: bool,
    token_name: str | None,
    token_symbol: str | None,
    source: str,
    reason: str | None,
) -> None:
    if not is_scam:
        return
    existing = await get_scam_token(session, contract_address)
    if existing is not None:
        return
    session.add(
        ScamToken(
            contract_address=contract_address,
            token_name=token_name,
            token_symbol=token_symbol,
            source=source,
            reason=reason,
        )
    )
    await session.commit()


async def get_payment_by_tx(session: AsyncSession, tx_id: str) -> PlanPayment | None:
    result = await session.execute(select(PlanPayment).where(PlanPayment.tx_id == tx_id))
    return result.scalar_one_or_none()


async def create_payment(session: AsyncSession, telegram_id: int, tx_id: str, amount_usdt: float) -> PlanPayment:
    payment = PlanPayment(telegram_id=telegram_id, tx_id=tx_id, amount_usdt=amount_usdt)
    session.add(payment)
    await session.commit()
    return payment


async def confirm_payment(session: AsyncSession, payment: PlanPayment, pro_plan_days: int) -> User:
    payment.status = PlanPaymentStatus.confirmed
    payment.confirmed_at = datetime.now(timezone.utc)
    user = await session.get(User, payment.telegram_id)
    user.plan = PlanType.pro
    user.plan_expires_at = datetime.now(timezone.utc) + timedelta(days=pro_plan_days)
    await session.commit()
    return user


async def reject_payment(session: AsyncSession, payment: PlanPayment) -> None:
    payment.status = PlanPaymentStatus.rejected
    await session.commit()


async def list_expiring_pro_users(session: AsyncSession, within_days: int) -> list[User]:
    now = datetime.now(timezone.utc)
    threshold = now + timedelta(days=within_days)
    result = await session.execute(
        select(User).where(
            User.plan == PlanType.pro,
            User.plan_expires_at.is_not(None),
            User.plan_expires_at <= threshold,
            User.plan_expires_at > now,
        )
    )
    return list(result.scalars().all())


async def list_expired_pro_users(session: AsyncSession) -> list[User]:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(User).where(
            User.plan == PlanType.pro,
            User.plan_expires_at.is_not(None),
            User.plan_expires_at <= now,
        )
    )
    return list(result.scalars().all())


async def downgrade_user(session: AsyncSession, user: User) -> None:
    user.plan = PlanType.free
    await session.commit()
