import re
from datetime import datetime, timedelta, timezone

from config import KST_OFFSET_HOURS

_MD_ESCAPE_RE = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")


def escape_md(text: str) -> str:
    return _MD_ESCAPE_RE.sub(r"\\\1", str(text))


def short_address(address: str, head: int = 4, tail: int = 4) -> str:
    if len(address) <= head + tail:
        return address
    return f"{address[:head]}...{address[-tail:]}"


def format_amount(amount: float, sign: bool = False) -> str:
    value = float(amount)
    prefix = "+" if sign and value >= 0 else ""
    return f"{prefix}{value:,.2f}"


def to_kst(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone(timedelta(hours=KST_OFFSET_HOURS)))


def format_datetime_kst(dt: datetime) -> str:
    return to_kst(dt).strftime("%Y-%m-%d %H:%M:%S") + " KST"


def scam_warning_block(token_name: str, contract_address: str) -> str:
    lines = [
        f"> ⚠️ *스캠 토큰 경고\\!*",
        f"> 이 거래의 토큰은 *공식 USDT가 아닙니다\\.*",
        ">",
        f"> 🪙 토큰명: `{escape_md(token_name)}`",
        f"> 📍 컨트랙트: `{contract_address}`",
        "> 📌 출처: TronScan 스캠 태그",
        ">",
        "> _이 토큰은 가치가 없거나 피싱 목적일 수 있습니다\\._",
        "> _절대 판매하거나 승인\\(approve\\)하지 마세요\\._",
    ]
    return "\n".join(lines)


def wallet_summary(address: str, balance: float, transactions: list[dict]) -> str:
    lines = [
        "💼 *지갑 조회 결과*",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"📍 `{address}`",
        f"💰 *잔액: {escape_md(format_amount(balance))} USDT*",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📋 *최근 거래 \\({len(transactions)}건\\)*",
        "",
    ]
    for tx in transactions:
        emoji = "🟢" if tx["direction"] == "in" else "🔴"
        sign_label = "입금" if tx["direction"] == "in" else "출금"
        counterparty_label = "From" if tx["direction"] == "in" else "To"
        counterparty = tx["from_address"] if tx["direction"] == "in" else tx["to_address"]
        amount_str = format_amount(tx["amount_usdt"], sign=True) if tx["direction"] == "in" else f"-{format_amount(tx['amount_usdt'])}"
        lines.append(f"{emoji} *{escape_md(amount_str)} USDT* {sign_label}")
        lines.append(f"   👤 {counterparty_label}: `{short_address(counterparty)}`")
        lines.append(f"   _{escape_md(format_datetime_kst(tx['block_timestamp']))}_")
        lines.append(f"   🔗 `{short_address(tx['tx_id'], 8, 0)}` \\[TronScan\\]")
        if tx.get("is_scam_token"):
            lines.append("> ⚠️ *스캠 토큰 감지* 1건 — 아래 참고")
        lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def deposit_alert(label: str, address: str, amount: float, from_address: str, tx_id: str, block_timestamp: datetime) -> str:
    return "\n".join(
        [
            "🟢 *USDT 입금 알림*",
            "━━━━━━━━━━━━━━━━━━━━",
            "",
            f"💼 *{escape_md(label)}* \\(`{short_address(address)}`\\)",
            f"📥 *\\+{escape_md(format_amount(amount))} USDT* 받음",
            "",
            "👤 *보낸 주소*",
            f"   `{short_address(from_address)}`",
            f"📅 _{escape_md(format_datetime_kst(block_timestamp))}_",
            f"🔗 `{tx_id}`",
            "",
            "━━━━━━━━━━━━━━━━━━━━",
            "✅ 정상 USDT 토큰 확인됨",
        ]
    )


def withdrawal_alert(
    label: str, address: str, amount: float, to_address: str, fee_trx: float, tx_id: str, block_timestamp: datetime
) -> str:
    return "\n".join(
        [
            "🔴 *USDT 출금 알림*",
            "━━━━━━━━━━━━━━━━━━━━",
            "",
            f"💼 *{escape_md(label)}* \\(`{short_address(address)}`\\)",
            f"📤 *\\-{escape_md(format_amount(amount))} USDT* 전송",
            "",
            "👤 *받는 주소*",
            f"   `{short_address(to_address)}`",
            f"💸 *수수료:* _{escape_md(format_amount(fee_trx))} TRX_",
            f"📅 _{escape_md(format_datetime_kst(block_timestamp))}_",
            f"🔗 `{tx_id}`",
            "",
            "━━━━━━━━━━━━━━━━━━━━",
        ]
    )
