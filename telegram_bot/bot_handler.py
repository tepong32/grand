import os
import django
import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import Update
from telegram.ext import CallbackContext
from django.utils import timezone
import sys
sys.path.append('/home/abutdtks/test.abutchikikz.online')

from dotenv import load_dotenv
load_dotenv()  # take environment variables

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'src.settings.prod')  # adjust if needed
django.setup()

from assistance.models import AssistanceRequest

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "PASTE-YOUR-BOT-TOKEN-HERE"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        "👋 Hello! To link your assistance request, please reply with:\n\n"
        "`your-refcode::editcode`\n\n"
        "Example:\n`MSWD-06-2025-0006::ab1234`\n\n"
        "If you'd like to unlink this account later, send `/unlink`.",
        parse_mode="Markdown"
    )


def unlink(update: Update, context: CallbackContext) -> None:
    chat_id = str(update.message.chat_id)
    try:
        updated = AssistanceRequest.objects.filter(
            telegram_chat_id=chat_id,
            claimed_at__isnull=True
        ).update(telegram_chat_id=None)
        if updated:
            update.message.reply_text("✅ Telegram account successfully unlinked.")
        else:
            update.message.reply_text("ℹ️ No active linked request found.")
    except Exception as e:
        logger.error(f"[TG UNLINK ERROR] {e}")
        update.message.reply_text("⚠️ An error occurred while trying to unlink. Please try again later.")


def handle_message(update: Update, context: CallbackContext) -> None:
    try:
        text = update.message.text.strip()
        chat_id = str(update.message.chat_id)

        if "::" not in text:
            update.message.reply_text("⚠️ Invalid format. Please send your reference code and edit code like:\n`MSWD-01-2025-0001::123456`", parse_mode="Markdown")
            return

        ref_code, edit_code = map(str.strip, text.split("::", 1))

        try:
            request = AssistanceRequest.objects.get(
                reference_code__iexact=ref_code,
                edit_code=edit_code,
                claimed_at__isnull=True
            )
        except AssistanceRequest.DoesNotExist:
            update.message.reply_text("❌ Request not found or already finalized.")
            return

        # Link Telegram chat
        request.telegram_chat_id = chat_id
        request.save(update_fields=["telegram_chat_id"])

        update.message.reply_text(
            f"✅ Linked successfully to *{request.full_name}*.\n\n"
            f"You will now receive status updates via Telegram.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"[TG MESSAGE ERROR] {e}")
        update.message.reply_text("⚠️ Something went wrong. Please try again later.")


def main():
    try:
        updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
        dispatcher = updater.dispatcher

        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("unlink", unlink))
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

        updater.start_polling()
        logger.info("🤖 Telegram bot polling started...")
        updater.idle()
    except Exception as e:
        logger.error(f"[TG BOT START ERROR] {e}")


if __name__ == '__main__':
    main()
