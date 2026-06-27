from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import runtime_state
from config import ADMIN_IDS, PRO_PLAN_DAYS
from db.engine import get_session
from db.models import PlanPayment, PlanPaymentStatus, PlanType, ScamToken, Transaction, User, WalletAddress
from utils.formatter import escape_md
from utils.validators import is_tron_address


def is_admin(telegram_id: int) -> bool:
    return telegram_id in ADMIN_IDS


async def _reply(update: Update, text: str, keyboard: InlineKeyboardMarkup | None = None) -> None:
    target = update.message or update.callback_query.message
    await target.reply_text(text, parse_mode="MarkdownV2", reply_markup=keyboard)


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return

    async with get_session() as session:
        total_users = (await session.execute(select(func.count(User.telegram_id)))).scalar_one()
        pro_users = (await session.execute(select(func.count(User.telegram_id)).where(User.plan == PlanType.pro))).scalar_one()
        total_wallets = (await session.execute(select(func.count(WalletAddress.id)))).scalar_one()
        scam_tokens = (await session.execute(select(func.count(ScamToken.id)))).scalar_one()

    text = (
        "👑 *관리자 패널*\n━━━━━━━━━━━━━━━━━\n\n"
        "📊 현재 현황:\n"
        f"👥 전체 유저: *{total_users}명*\n"
        f"💎 Pro 유저:  *{pro_users}명*\n"
        f"💼 등록 지갑: *{total_wallets}개*\n"
        f"🚨 스캠 토큰: *{scam_tokens}개* 등록됨\n\n"
        "━━━━━━━━━━━━━━━━━"
    )
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("👥 유저 관리", callback_data="admin:users"), InlineKeyboardButton("💳 결제 내역", callback_data="admin:payments")],
            [InlineKeyboardButton("🚨 스캠 토큰 관리", callback_data="admin:scam"), InlineKeyboardButton("📢 공지 발송", callback_data="admin:broadcast")],
            [InlineKeyboardButton("📊 전체 통계", callback_data="admin:stats"), InlineKeyboardButton("⚙️ 봇 설정", callback_data="admin:settings")],
            [InlineKeyboardButton("🔴 긴급 봇 정지", callback_data="admin:halt")],
        ]
    )
    await _reply(update, text, keyboard)


async def search_user(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
    if not is_admin(update.effective_user.id):
        return

    async with get_session() as session:
        user = None
        if query.isdigit():
            user = await session.get(User, int(query))
        else:
            handle = query.lstrip("@")
            result = await session.execute(select(User).where(User.username == handle))
            user = result.scalar_one_or_none()

        if user is None:
            await _reply(update, "❌ 유저를 찾을 수 없습니다\\.")
            return

        wallets = await session.execute(select(func.count(WalletAddress.id)).where(WalletAddress.telegram_id == user.telegram_id))
        wallet_count = wallets.scalar_one()

    expires = user.plan_expires_at.strftime("%Y-%m-%d") if user.plan_expires_at else "-"
    created = user.created_at.strftime("%Y-%m-%d")
    text = (
        "👤 *유저 정보*\n━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: `{user.telegram_id}`\n"
        f"📛 Username: @{escape_md(user.username or '-')}\n"
        f"👑 플랜: *{user.plan.value.capitalize()}* \\(~{escape_md(expires)}\\)\n"
        f"💼 등록 주소: {wallet_count}개\n"
        f"📅 가입일: _{escape_md(created)}_\n"
        "━━━━━━━━━━━━━━━━━"
    )
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("👑 Pro 부여", callback_data=f"admin:grant_pro:{user.telegram_id}"), InlineKeyboardButton("🔴 Free 강등", callback_data=f"admin:demote:{user.telegram_id}")],
            [InlineKeyboardButton("🚫 차단", callback_data=f"admin:ban:{user.telegram_id}"), InlineKeyboardButton("◀ 뒤로", callback_data="admin:users")],
        ]
    )
    await _reply(update, text, keyboard)


async def grant_pro(update: Update, context: ContextTypes.DEFAULT_TYPE, telegram_id: int) -> None:
    if not is_admin(update.effective_user.id):
        return
    async with get_session() as session:
        user = await session.get(User, telegram_id)
        if user is None:
            await _reply(update, "❌ 유저를 찾을 수 없습니다\\.")
            return
        user.plan = PlanType.pro
        user.plan_expires_at = datetime.now(timezone.utc) + timedelta(days=PRO_PLAN_DAYS)
        await session.commit()
    await _reply(update, f"👑 유저 `{telegram_id}`에게 Pro 플랜을 부여했습니다\\.")


async def demote_to_free(update: Update, context: ContextTypes.DEFAULT_TYPE, telegram_id: int) -> None:
    if not is_admin(update.effective_user.id):
        return
    async with get_session() as session:
        user = await session.get(User, telegram_id)
        if user is None:
            await _reply(update, "❌ 유저를 찾을 수 없습니다\\.")
            return
        user.plan = PlanType.free
        user.plan_expires_at = None
        await session.commit()
    await _reply(update, f"🔴 유저 `{telegram_id}`를 Free로 강등했습니다\\.")


async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE, telegram_id: int) -> None:
    if not is_admin(update.effective_user.id):
        return
    async with get_session() as session:
        user = await session.get(User, telegram_id)
        if user is None:
            await _reply(update, "❌ 유저를 찾을 수 없습니다\\.")
            return
        user.is_banned = True
        await session.commit()
    await _reply(update, f"🚫 유저 `{telegram_id}`를 차단했습니다\\.")


async def list_scam_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return
    async with get_session() as session:
        result = await session.execute(select(ScamToken).order_by(ScamToken.id))
        tokens = list(result.scalars().all())

    lines = ["🚨 *스캠 토큰 DB*", "━━━━━━━━━━━━━━━━━", f"총 *{len(tokens)}개* 등록됨", ""]
    for idx, token in enumerate(tokens[:20], start=1):
        lines.append(f"{idx}\\. `{token.contract_address}` — {escape_md(token.token_name or '-')}")
    lines.append("━━━━━━━━━━━━━━━━━")

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🟢 수동 추가", callback_data="admin:scam_add"), InlineKeyboardButton("🔴 삭제", callback_data="admin:scam_delete")],
            [InlineKeyboardButton("🔄 TronScan 동기화", callback_data="admin:scam_sync")],
            [InlineKeyboardButton("◀ 관리자 메인", callback_data="admin:home")],
        ]
    )
    await _reply(update, "\n".join(lines), keyboard)


async def list_payments(update: Update, context: ContextTypes.DEFAULT_TYPE, limit: int = 15) -> None:
    if not is_admin(update.effective_user.id):
        return
    async with get_session() as session:
        result = await session.execute(select(PlanPayment).order_by(PlanPayment.created_at.desc()).limit(limit))
        payments = list(result.scalars().all())

    lines = ["💳 *결제 내역*", "━━━━━━━━━━━━━━━━━", ""]
    if not payments:
        lines.append("결제 내역이 없습니다\\.")
    for payment in payments:
        status_emoji = {"confirmed": "🟢", "pending": "🟡", "rejected": "🔴"}.get(payment.status.value, "⚪")
        lines.append(
            f"{status_emoji} `{payment.telegram_id}` — *{escape_md(f'{float(payment.amount_usdt):.2f}')} USDT*"
        )
        lines.append(f"   _{escape_md(payment.created_at.strftime('%Y-%m-%d %H:%M'))}_ — `{payment.tx_id[:16]}…`")
        lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━")

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("◀ 관리자 메인", callback_data="admin:home")]])
    await _reply(update, "\n".join(lines), keyboard)


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return

    from config import (
        OWNER_WALLET_ADDRESS,
        POLL_INTERVAL_SECONDS,
        PRICE_CHECK_INTERVAL_SECONDS,
        PRO_PLAN_USDT_PRICE,
    )

    halt_state = "🔴 정지됨" if runtime_state.is_halted() else "🟢 정상 운영"
    text = (
        "⚙️ *봇 설정*\n━━━━━━━━━━━━━━━━━\n\n"
        f"📡 폴링 주기: *{POLL_INTERVAL_SECONDS}초*\n"
        f"📈 시세 체크 주기: *{PRICE_CHECK_INTERVAL_SECONDS}초*\n"
        f"💎 Pro 플랜 가격: *{escape_md(str(PRO_PLAN_USDT_PRICE))} USDT*\n"
        f"📅 Pro 플랜 기간: *{PRO_PLAN_DAYS}일*\n"
        f"🏦 오너 지갑: `{OWNER_WALLET_ADDRESS}`\n"
        f"🚦 봇 상태: *{halt_state}*\n"
        "━━━━━━━━━━━━━━━━━"
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("◀ 관리자 메인", callback_data="admin:home")]])
    await _reply(update, text, keyboard)


async def toggle_halt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return
    runtime_state.set_halted(not runtime_state.is_halted())
    state_str = "🔴 긴급 정지되었습니다" if runtime_state.is_halted() else "🟢 정상 운영으로 복귀했습니다"
    await _reply(update, f"봇이 {state_str}\\.")


async def prompt_scam_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return
    context.user_data["awaiting"] = "scam_add"
    await _reply(update, "🟢 스캠으로 등록할 컨트랙트 주소를 입력해주세요\\.")


async def prompt_scam_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return
    context.user_data["awaiting"] = "scam_delete"
    await _reply(update, "🔴 삭제할 스캠 컨트랙트 주소를 입력해주세요\\.")


async def sync_scam_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return
    await _reply(update, "🔄 TronScan 동기화는 현재 준비 중입니다\\. 수동 추가/삭제를 이용해주세요\\.")


async def prompt_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return
    context.user_data["awaiting"] = "broadcast"
    await _reply(update, "📢 전체 유저에게 발송할 공지 내용을 입력해주세요\\.")


async def add_scam_token(update: Update, context: ContextTypes.DEFAULT_TYPE, contract_address: str, reason: str | None = None) -> None:
    if not is_admin(update.effective_user.id):
        return
    if not is_tron_address(contract_address):
        await _reply(update, "❌ 올바른 트론 컨트랙트 주소가 아닙니다\\.")
        return

    async with get_session() as session:
        existing = await session.execute(select(ScamToken).where(ScamToken.contract_address == contract_address))
        if existing.scalar_one_or_none() is not None:
            await _reply(update, "이미 등록된 스캠 토큰입니다\\.")
            return
        session.add(ScamToken(contract_address=contract_address, source="manual", reason=reason))
        await session.commit()
    await _reply(update, f"🟢 스캠 토큰이 등록되었습니다: `{contract_address}`")


async def delete_scam_token(update: Update, context: ContextTypes.DEFAULT_TYPE, contract_address: str) -> None:
    if not is_admin(update.effective_user.id):
        return
    async with get_session() as session:
        result = await session.execute(select(ScamToken).where(ScamToken.contract_address == contract_address))
        token = result.scalar_one_or_none()
        if token is None:
            await _reply(update, "❌ 등록되지 않은 토큰입니다\\.")
            return
        await session.delete(token)
        await session.commit()
    await _reply(update, f"🔴 스캠 토큰이 삭제되었습니다: `{contract_address}`")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, target: str = "all") -> None:
    if not is_admin(update.effective_user.id):
        return

    async with get_session() as session:
        if target == "pro":
            result = await session.execute(select(User.telegram_id).where(User.plan == PlanType.pro))
        else:
            result = await session.execute(select(User.telegram_id))
        ids = [row[0] for row in result.all()]

    sent = 0
    for telegram_id in ids:
        try:
            await context.bot.send_message(chat_id=telegram_id, text=text)
            sent += 1
        except Exception:
            continue
    await _reply(update, f"📢 공지를 {sent}명에게 발송했습니다\\.")


async def full_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    async with get_session() as session:
        total_users = (await session.execute(select(func.count(User.telegram_id)))).scalar_one()
        new_today = (await session.execute(select(func.count(User.telegram_id)).where(User.created_at >= today_start))).scalar_one()
        pro_users = (await session.execute(select(func.count(User.telegram_id)).where(User.plan == PlanType.pro))).scalar_one()
        total_wallets = (await session.execute(select(func.count(WalletAddress.id)))).scalar_one()
        notif_today = (await session.execute(select(func.count(Transaction.id)).where(Transaction.block_timestamp >= today_start))).scalar_one()
        monthly_revenue = (
            await session.execute(
                select(func.coalesce(func.sum(PlanPayment.amount_usdt), 0)).where(
                    PlanPayment.created_at >= month_start, PlanPayment.status == "confirmed"
                )
            )
        ).scalar_one()
        scam_today = (await session.execute(select(func.count(Transaction.id)).where(Transaction.block_timestamp >= today_start, Transaction.is_scam_token.is_(True)))).scalar_one()
        scam_total = (await session.execute(select(func.count(Transaction.id)).where(Transaction.is_scam_token.is_(True)))).scalar_one()

    pro_ratio = (pro_users / total_users * 100) if total_users else 0
    text = (
        "📊 *서비스 전체 통계*\n━━━━━━━━━━━━━━━━━\n"
        f"_{escape_md(now.strftime('%Y-%m-%d'))} 기준_\n\n"
        "👥 *유저*\n"
        f"  전체: *{total_users}명*\n"
        f"  오늘 신규: *\\+{new_today}명*\n"
        f"  Pro: *{pro_users}명* \\({escape_md(f'{pro_ratio:.1f}')}%\\)\n\n"
        "💼 *지갑*\n"
        f"  전체 등록: *{total_wallets}개*\n"
        f"  오늘 알림 발송: *{notif_today}건*\n\n"
        "💰 *수익*\n"
        f"  이번 달: *\\+{escape_md(f'{float(monthly_revenue):.0f}')} USDT*\n\n"
        "🚨 *스캠*\n"
        f"  오늘 감지: *{scam_today}건*\n"
        f"  누적 차단: *{scam_total}건*\n"
        "━━━━━━━━━━━━━━━━━"
    )
    await _reply(update, text)
