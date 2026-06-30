import enum
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PlanType(str, enum.Enum):
    free = "free"
    pro = "pro"


class TxDirection(str, enum.Enum):
    in_ = "in"
    out = "out"


class PlanPaymentStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    rejected = "rejected"


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    plan: Mapped[PlanType] = mapped_column(Enum(PlanType), default=PlanType.free)
    plan_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    price_alert_on: Mapped[bool] = mapped_column(Boolean, default=False)
    price_alert_target: Mapped[float | None] = mapped_column(Numeric(20, 6), nullable=True)
    price_report_on: Mapped[bool] = mapped_column(Boolean, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    min_alert_amount: Mapped[float] = mapped_column(Numeric(20, 6), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    wallets: Mapped[list["WalletAddress"]] = relationship(back_populates="user")
    payments: Mapped[list["PlanPayment"]] = relationship(back_populates="user")


class WalletAddress(Base):
    __tablename__ = "wallet_addresses"
    __table_args__ = (UniqueConstraint("telegram_id", "address", name="uq_user_address"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    address: Mapped[str] = mapped_column(String(34))
    label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_tx_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user: Mapped["User"] = relationship(back_populates="wallets")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="wallet")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    wallet_address_id: Mapped[int] = mapped_column(ForeignKey("wallet_addresses.id"))
    tx_id: Mapped[str] = mapped_column(String(64), unique=True)
    direction: Mapped[TxDirection] = mapped_column(Enum(TxDirection))
    amount_usdt: Mapped[float] = mapped_column(Numeric(20, 6))
    from_address: Mapped[str] = mapped_column(String(34))
    to_address: Mapped[str] = mapped_column(String(34))
    token_contract: Mapped[str] = mapped_column(String(34))
    is_scam_token: Mapped[bool] = mapped_column(Boolean, default=False)
    block_timestamp: Mapped[datetime] = mapped_column(DateTime)
    fee_trx: Mapped[float] = mapped_column(Numeric(20, 6), default=0)

    wallet: Mapped["WalletAddress"] = relationship(back_populates="transactions")


class ScamToken(Base):
    __tablename__ = "scam_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contract_address: Mapped[str] = mapped_column(String(34), unique=True)
    token_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    token_symbol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source: Mapped[str] = mapped_column(String(50))
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PlanPayment(Base):
    __tablename__ = "plan_payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"))
    tx_id: Mapped[str] = mapped_column(String(64), unique=True)
    amount_usdt: Mapped[float] = mapped_column(Numeric(20, 6))
    status: Mapped[PlanPaymentStatus] = mapped_column(Enum(PlanPaymentStatus), default=PlanPaymentStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="payments")
