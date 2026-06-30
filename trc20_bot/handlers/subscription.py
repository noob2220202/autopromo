from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import OWNER_WALLET_ADDRESS, PLAN_12M_PRICE, PLAN_1M_PRICE, PLAN_3M_PRICE, USDT_CONTRACT
from db import crud
from db.engine import get_session
from db.models import PlanPayment
from services import trongrid
from utils.respond import respond

PLANS = {
    "1m": {"label": "1개월", "price": PLAN_1M_PRICE, "days": 30},
    "3m": {"label": "3개월", "price": PLAN_3M_PRICE, "days": 90},
    "12m": {"label": "1년", "price": PLAN_12M_PRICE, "days": 365},
}

PLAN_MENU_TEXT = (
    "👑 프리미엄 멤버십\n\n"
    "프리미엄으로 업그레이드하고\n"
    "더 많은 혜택을 누리세요!\n\n"
    "프리미엄 혜택:\n"
    "✨ 지갑 5개까지 등록 (무료: 1개)\n"
    "✨ 알림 광고 완전 제거\n"
    "✨ 우선 고객 지원\n"
    "✨ 추후 추가 기능 우선 제공\n\n"
    "가격:\n"
    f"• 1개월: {PLAN_1M_PRICE:.0f} USDT\n"
    f"• 3개월: {PLAN_3M_PRICE:.0f} USDT (월 {PLAN_3M_PRICE/3:.1f} USDT)\n"
    f"• 1년: {PLAN_12M_PRICE:.0f} USDT (월 {PLAN_12M_PRICE/12:.1f} USDT)\n\n"
    "아래에서 플랜을 선택하세요 👇"
)

PLAN_MENU_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton(f"1개월 - {PLAN_1M_PRICE:.0f} USDT", callback_data="plan:select:1m")],
        [InlineKeyboardButton(f"3개월 - {PLAN_3M_PRICE:.0f} USDT 💎", callback_data="plan:select:3m")],
        [InlineKeyboardButton(f"1년 - {PLAN_12M_PRICE:.0f} USDT 👑", callback_data="plan:select:12m")],
        [InlineKeyboardButton("◀ 메인 메뉴", callback_data="menu:home")],
    ]
)


async def show_plan_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    async with get_session() as session:
        wallets = await crud.list_wallets(session, telegram_id)

    if not wallets:
        await respond(
            update,
            "❌ 등록된 지갑이 없습니다!\n\n"
            "프리미엄 결제를 위해서는 먼저 지갑을\n"
            "등록해야 합니다.\n\n"
            "1️⃣ 메인 메뉴에서 '➕ 지갑 추가'를 선택\n"
            "2️⃣ /p [지갑주소] 형식으로 지갑 등록\n"
            "3️⃣ 다시 프리미엄 구매를 시도해주세요\n\n"
            "⚠️ 등록된 지갑에서만 결제가 가능합니다!",
            InlineKeyboardMarkup([[InlineKeyboardButton("◀ 메인 메뉴", callback_data="menu:home")]]),
        )
        return

    await respond(update, PLAN_MENU_TEXT, PLAN_MENU_KEYBOARD)


async def show_plan_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_id: str) -> None:
    plan = PLANS.get(plan_id)
    if plan is None:
        await respond(update, "❌ 잘못된 플랜입니다.")
        return

    telegram_id = update.effective_user.id
    async with get_session() as session:
        wallets = await crud.list_wallets(session, telegram_id)

    if not wallets:
        await respond(
            update,
            "❌ 등록된 지갑이 없습니다!\n먼저 /p [지갑주소] 로 지갑을 등록해주세요.",
            InlineKeyboardMarkup([[InlineKeyboardButton("◀ 메인 메뉴", callback_data="menu:home")]]),
        )
        return

    wallet_lines = "\n".join(f"• {w.address}" for w in wallets)
    text = (
        "💳 프리미엄 결제 안내\n\n"
        f"📦 선택한 플랜: {plan['label']}\n"
        f"💰 금액: {plan['price']:.0f} USDT\n\n"
        "⚠️ 중요: 등록된 지갑에서만 결제 가능!\n\n"
        "귀하의 등록 지갑:\n"
        f"{wallet_lines}\n\n"
        "결제 방법:\n"
        f"1️⃣ 위 지갑 중 하나에서\n"
        f"2️⃣ 아래 주소로 정확히 {plan['price']:.0f} USDT 전송\n\n"
        f"📍 입금 지갑:\n{OWNER_WALLET_ADDRESS}\n\n"
        "⚠️ 주의사항:\n"
        "- 반드시 등록된 지갑에서 전송하세요\n"
        "- TRC20 네트워크 사용\n"
        f"- 정확히 {plan['price']:.0f} USDT 전송\n"
        "- 15분 이내 자동 처리\n\n"
        "🔄 입금을 감지하는 중입니다..."
    )
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ 입금 완료", callback_data=f"plan:check:{plan_id}")],
            [InlineKeyboardButton("◀ 취소", callback_data="menu:plan")],
        ]
    )
    await respond(update, text, keyboard)


async def check_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_id: str) -> None:
    plan = PLANS.get(plan_id)
    if plan is None:
        await respond(update, "❌ 잘못된 플랜입니다.")
        return

    telegram_id = update.effective_user.id
    target_amount = plan["price"]
    plan_days = plan["days"]
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)

    async with get_session() as session:
        wallets = await crud.list_wallets(session, telegram_id)
        if not wallets:
            await respond(update, "❌ 등록된 지갑이 없습니다.")
            return
        registered_addresses = {w.address for w in wallets}

        for wallet in wallets:
            raw_txs = await trongrid.get_trc20_transactions(wallet.address, limit=20, contract_address=USDT_CONTRACT)
            for tx in raw_txs:
                to_addr = tx.get("to", "")
                from_addr = tx.get("from", "")
                amount = int(tx.get("value", 0)) / 1_000_000
                ts_ms = tx.get("block_timestamp", 0)
                block_time = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
                tx_id = tx.get("transaction_id", "")

                if not (
                    to_addr == OWNER_WALLET_ADDRESS
                    and from_addr in registered_addresses
                    and abs(amount - target_amount) < 0.01
                    and block_time >= cutoff
                ):
                    continue

                existing = await session.execute(
                    select(PlanPayment).where(PlanPayment.tx_id == tx_id)
                )
                if existing.scalar_one_or_none() is not None:
                    await respond(update, "이미 처리된 결제입니다.")
                    return

                payment = await crud.create_payment(session, telegram_id, tx_id, amount)
                user = await crud.confirm_payment(session, payment, pro_plan_days=plan_days)
                expires_str = user.plan_expires_at.strftime("%Y-%m-%d") if user.plan_expires_at else "-"
                await respond(
                    update,
                    f"✅ 프리미엄 활성화 완료!\n\n"
                    f"👑 플랜: {plan['label']} 프리미엄\n"
                    f"📅 만료일: {expires_str}\n"
                    "📍 지갑 한도: 최대 5개\n\n"
                    f"🔗 확인된 TX: {tx_id[:16]}...\n\n"
                    "이제 모든 프리미엄 기능을 이용하실 수 있습니다!",
                    InlineKeyboardMarkup([[InlineKeyboardButton("◀ 메인 메뉴", callback_data="menu:home")]]),
                )
                return

        await respond(
            update,
            f"🔄 아직 {target_amount:.0f} USDT 입금이 확인되지 않았습니다.\n\n"
            "전송 후 네트워크 처리에 최대 2-3분이 소요될 수 있습니다.\n"
            "잠시 후 다시 확인해주세요.",
            InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🔄 다시 확인", callback_data=f"plan:check:{plan_id}")],
                    [InlineKeyboardButton("◀ 취소", callback_data="menu:plan")],
                ]
            ),
        )
