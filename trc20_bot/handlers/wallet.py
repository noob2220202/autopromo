from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import FREE_PLAN_WALLET_LIMIT, PRO_PLAN_WALLET_LIMIT
from db import crud
from db.engine import get_session
from db.models import PlanType
from services import trongrid
from utils.formatter import escape_md, format_amount, short_address
from utils.validators import is_tron_address


def _limit_for_plan(plan: PlanType) -> int:
    return PRO_PLAN_WALLET_LIMIT if plan == PlanType.pro else FREE_PLAN_WALLET_LIMIT


async def show_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    async with get_session() as session:
        user = await crud.get_or_create_user(session, telegram_id, update.effective_user.username)
        plan = await crud.get_active_plan(user)
        wallets = await crud.list_wallets(session, telegram_id)

    limit = _limit_for_plan(plan)
    lines = [
        "💼 *내 등록 지갑*",
        "━━━━━━━━━━━━━━━━━",
        f"👤 플랜: *{plan.value.capitalize()}* \\| 사용 {len(wallets)} / {limit}",
        "",
    ]
    for idx, wallet in enumerate(wallets, start=1):
        balance = await trongrid.get_balance(wallet.address)
        label = wallet.label or "지갑"
        status = "🟢 알림 활성" if wallet.is_active else "🔴 알림 비활성"
        lines += [
            f"{idx}\\u20e3 🏷️ _{escape_md(label)}_",
            f"   `{wallet.address}`",
            f"   💰 *{escape_md(format_amount(balance))} USDT*",
            f"   {status}",
            "",
        ]
    lines.append("━━━━━━━━━━━━━━━━━")

    buttons = [[InlineKeyboardButton("🟢 주소 추가", callback_data="wallet:prompt_add")]]
    for idx, wallet in enumerate(wallets, start=1):
        buttons.append(
            [
                InlineKeyboardButton(f"🔵 {idx}번 상세보기", callback_data=f"wallet:detail:{wallet.id}"),
                InlineKeyboardButton(f"🔴 {idx}번 삭제", callback_data=f"wallet:delete:{wallet.id}"),
            ]
        )
    buttons.append([InlineKeyboardButton("🏠 메인으로", callback_data="menu:home")])

    message = "\n".join(lines)
    target = update.message or update.callback_query.message
    await target.reply_text(message, parse_mode="MarkdownV2", reply_markup=InlineKeyboardMarkup(buttons))


async def add_wallet_from_address(update: Update, context: ContextTypes.DEFAULT_TYPE, address: str) -> None:
    telegram_id = update.effective_user.id
    if not is_tron_address(address):
        return

    async with get_session() as session:
        user = await crud.get_or_create_user(session, telegram_id, update.effective_user.username)
        plan = await crud.get_active_plan(user)
        wallets = await crud.list_wallets(session, telegram_id)
        limit = _limit_for_plan(plan)

        if len(wallets) >= limit:
            target = update.message or update.callback_query.message
            await target.reply_text(
                "> 💳 *Pro 플랜이 필요합니다*\n\n"
                f"무료 플랜은 주소 *{FREE_PLAN_WALLET_LIMIT}개*만 등록할 수 있어요\\.\n"
                f"Pro 플랜으로 업그레이드하면 최대 *{PRO_PLAN_WALLET_LIMIT}개*까지 등록 가능합니다\\.",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("💳 Pro 플랜 보기", callback_data="menu:plan")],
                        [InlineKeyboardButton("🏠 메인으로", callback_data="menu:home")],
                    ]
                ),
            )
            return

        await crud.add_wallet(session, telegram_id, address, label=None)

    target = update.message or update.callback_query.message
    await target.reply_text(f"🟢 지갑이 등록되었습니다: `{address}`", parse_mode="MarkdownV2")


async def delete_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE, wallet_id: int) -> None:
    telegram_id = update.effective_user.id
    async with get_session() as session:
        deleted = await crud.delete_wallet(session, wallet_id, telegram_id)

    target = update.message or update.callback_query.message
    if deleted:
        await target.reply_text("🔴 지갑이 삭제되었습니다\\.", parse_mode="MarkdownV2")
    else:
        await target.reply_text("❌ 삭제할 지갑을 찾을 수 없습니다\\.", parse_mode="MarkdownV2")


async def prompt_add_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = update.message or update.callback_query.message
    await target.reply_text(
        "🟢 등록할 트론\\(Tron\\) 지갑 주소를 채팅창에 입력해주세요\\.\n"
        "주소를 보내면 잔액 조회 결과와 함께 *\\[🟢 이 주소 등록\\]* 버튼이 나타납니다\\.",
        parse_mode="MarkdownV2",
    )


async def wallet_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, wallet_id: int) -> None:
    telegram_id = update.effective_user.id
    async with get_session() as session:
        wallets = await crud.list_wallets(session, telegram_id)
    wallet = next((w for w in wallets if w.id == wallet_id), None)

    target = update.message or update.callback_query.message
    if wallet is None:
        await target.reply_text("❌ 지갑을 찾을 수 없습니다\\.", parse_mode="MarkdownV2")
        return

    balance = await trongrid.get_balance(wallet.address)
    label = wallet.label or "지갑"
    status = "🟢 알림 활성" if wallet.is_active else "🔴 알림 비활성"
    text = (
        f"🔵 *{escape_md(label)} 상세정보*\n━━━━━━━━━━━━━━━━━\n\n"
        f"📍 `{wallet.address}`\n"
        f"💰 *잔액: {escape_md(format_amount(balance))} USDT*\n"
        f"{status}\n"
        "━━━━━━━━━━━━━━━━━"
    )
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔗 TronScan에서 보기", url=f"https://tronscan.org/#/address/{wallet.address}")],
            [InlineKeyboardButton("🔴 삭제", callback_data=f"wallet:delete:{wallet.id}"), InlineKeyboardButton("◀ 뒤로", callback_data="menu:wallet")],
        ]
    )
    await target.reply_text(text, parse_mode="MarkdownV2", reply_markup=keyboard)
