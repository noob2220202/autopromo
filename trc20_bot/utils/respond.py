from telegram import InlineKeyboardMarkup, Update
from telegram.error import BadRequest


async def respond(
    update: Update,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
    parse_mode: str = "MarkdownV2",
) -> None:
    if update.callback_query is not None:
        try:
            await update.callback_query.edit_message_text(text, parse_mode=parse_mode, reply_markup=keyboard)
        except BadRequest as exc:
            if "Message is not modified" not in str(exc):
                raise
        return

    await update.message.reply_text(text, parse_mode=parse_mode, reply_markup=keyboard)
