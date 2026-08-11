from asgiref.sync import async_to_sync
from django.test import SimpleTestCase
from unittest.mock import AsyncMock, Mock, patch

from telegram.ext import CommandHandler, MessageHandler

from telegram_bot.bot_handler import build_application, handle_message, start, unlink


class TelegramBotHandlerTests(SimpleTestCase):
    def make_update(self, text=None, chat_id=12345):
        message = Mock(text=text)
        message.reply_text = AsyncMock()
        return Mock(effective_message=message, effective_chat=Mock(id=chat_id)), message

    def test_application_registers_current_async_handlers(self):
        application = build_application("123456:synthetic-token")

        handlers = application.handlers[0]

        self.assertEqual(len(handlers), 3)
        self.assertIsInstance(handlers[0], CommandHandler)
        self.assertIsInstance(handlers[1], CommandHandler)
        self.assertIsInstance(handlers[2], MessageHandler)

    def test_start_sends_linking_instructions(self):
        update, message = self.make_update()

        async_to_sync(start)(update, None)

        message.reply_text.assert_awaited_once()
        self.assertIn("your-refcode::editcode", message.reply_text.await_args.args[0])

    @patch("telegram_bot.bot_handler.unlink_chat_requests", return_value=1)
    def test_unlink_uses_effective_chat(self, unlink_requests):
        update, message = self.make_update(chat_id=98765)

        async_to_sync(unlink)(update, None)

        unlink_requests.assert_called_once_with(98765)
        message.reply_text.assert_awaited_once_with("Telegram account successfully unlinked.")

    def test_invalid_link_message_returns_format_help(self):
        update, message = self.make_update(text="not-a-link-token")

        async_to_sync(handle_message)(update, None)

        message.reply_text.assert_awaited_once()
        self.assertIn("Invalid format", message.reply_text.await_args.args[0])

    @patch("telegram_bot.bot_handler.link_chat_to_request")
    @patch("telegram_bot.bot_handler.find_request_by_reference")
    def test_valid_link_message_connects_request(self, find_request, link_request):
        request_obj = Mock(full_name="Synthetic Citizen")
        find_request.return_value = request_obj
        update, message = self.make_update(text="MSWD-TEST-001::654321", chat_id=24680)

        async_to_sync(handle_message)(update, None)

        find_request.assert_called_once_with("MSWD-TEST-001", "654321")
        link_request.assert_called_once_with(request_obj, chat_id=24680)
        message.reply_text.assert_awaited_once()
        self.assertIn("Linked successfully", message.reply_text.await_args.args[0])
