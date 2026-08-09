import logging
import os

from django.conf import settings
import django

from telegram import Update
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, Filters, Updater

from assistance.models import AssistanceRequest
from telegram_bot.services.bot_config import resolve_bot_token
from telegram_bot.services.message_service import parse_assistance_link_payload, find_request_by_reference, link_chat_to_request


def _configure_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", os.environ.get("DJANGO_SETTINGS_MODULE", "src.settings.prod"))
    if not settings.configured:
        django.setup()


def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        "Hello! To link your assistance request, reply with:\n\n"
        "`your-refcode::editcode`\n\n"
        "Example:\n`MSWD-01-2025-0001::123456`\n\n"
        "If you'd like to unlink this account later, send `/unlink`.",
        parse_mode="Markdown"
    )


def unlink(update: Update, context: CallbackContext) -> None:
    chat_id = str(update.message.chat_id)
    updated = AssistanceRequest.objects.filter(
        telegram_chat_id=chat_id,
        claimed_at__isnull=True
    ).update(telegram_chat_id=None)

    if updated:
        update.message.reply_text("Telegram account successfully unlinked.")
    else:
        update.message.reply_text("No active linked request found.")


def handle_message(update: Update, context: CallbackContext) -> None:
    try:
        text = (update.message.text or "").strip()
        parsed = parse_assistance_link_payload(text)
        if not parsed:
            update.message.reply_text(
                "Invalid format. Send `reference::editcode`.",
                parse_mode="Markdown"
            )
            return

        ref_code, edit_code = parsed
        request = find_request_by_reference(ref_code, edit_code)
        if not request:
            update.message.reply_text("Request not found or already claimed.")
            return

        link_chat_to_request(request, chat_id=str(update.message.chat_id))
        update.message.reply_text(
            f"Linked successfully to *{request.full_name}*.\n\n"
            "You will now receive status updates via Telegram.",
            parse_mode="Markdown"
        )
    except Exception as exc:
        logging.getLogger(__name__).error("[TG MESSAGE ERROR] %s", exc)
        update.message.reply_text("Something went wrong. Please try again later.")


def main():
    _configure_django()

    token = resolve_bot_token()
    if not token:
        logging.getLogger(__name__).error("Telegram token is not configured.")
        return

    try:
        updater = Updater(token=token, use_context=True)
        dispatcher = updater.dispatcher
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("unlink", unlink))
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

        updater.start_polling()
        logging.getLogger(__name__).info("Telegram bot polling started.")
        updater.idle()
    except Exception as exc:
        logging.getLogger(__name__).error("[TG BOT START ERROR] %s", exc)


if __name__ == "__main__":
    main()
