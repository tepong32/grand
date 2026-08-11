import logging
import os

from django.conf import settings
import django
from asgiref.sync import sync_to_async

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from telegram_bot.services.bot_config import resolve_bot_token
from telegram_bot.services.message_service import (
    find_request_by_reference,
    link_chat_to_request,
    parse_assistance_link_payload,
    unlink_chat_requests,
)


def _configure_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", os.environ.get("DJANGO_SETTINGS_MODULE", "src.settings.prod"))
    if not settings.configured:
        django.setup()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return

    await message.reply_text(
        "Hello! To link your assistance request, reply with:\n\n"
        "`your-refcode::editcode`\n\n"
        "Example:\n`MSWD-01-2025-0001::123456`\n\n"
        "If you'd like to unlink this account later, send `/unlink`.",
        parse_mode="Markdown"
    )


async def unlink(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None:
        return

    updated = await sync_to_async(unlink_chat_requests)(chat.id)
    if updated:
        await message.reply_text("Telegram account successfully unlinked.")
    else:
        await message.reply_text("No active linked request found.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None:
        return

    try:
        text = (message.text or "").strip()
        parsed = parse_assistance_link_payload(text)
        if not parsed:
            await message.reply_text(
                "Invalid format. Send `reference::editcode`.",
                parse_mode="Markdown"
            )
            return

        ref_code, edit_code = parsed
        request_obj = await sync_to_async(find_request_by_reference)(ref_code, edit_code)
        if not request_obj:
            await message.reply_text("Request not found or already claimed.")
            return

        await sync_to_async(link_chat_to_request)(request_obj, chat_id=chat.id)
        await message.reply_text(
            f"Linked successfully to *{request_obj.full_name}*.\n\n"
            "You will now receive status updates via Telegram.",
            parse_mode="Markdown"
        )
    except Exception as exc:
        logging.getLogger(__name__).error("[TG MESSAGE ERROR] %s", exc)
        await message.reply_text("Something went wrong. Please try again later.")


def build_application(token):
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("unlink", unlink))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return application


def main():
    _configure_django()

    token = resolve_bot_token()
    if not token:
        logging.getLogger(__name__).error("Telegram token is not configured.")
        return

    try:
        application = build_application(token)
        logging.getLogger(__name__).info("Telegram bot polling started.")
        application.run_polling()
    except Exception as exc:
        logging.getLogger(__name__).error("[TG BOT START ERROR] %s", exc)


if __name__ == "__main__":
    main()
