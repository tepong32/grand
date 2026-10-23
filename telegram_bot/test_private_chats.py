"""No credential handling, association writes or replies in non-private chats."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

from asgiref.sync import async_to_sync
from django.http import Http404
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from assistance.models import AssistanceRequest, AssistanceType
from telegram_bot.bot_handler import handle_message, start, unlink
from telegram_bot.services.message_service import link_chat_to_request


class PrivateChatHandlerTests(SimpleTestCase):
    def assert_chat_rejected(self, chat):
        message = Mock()
        type(message).text = PropertyMock(side_effect=AssertionError("Non-private credential was inspected"))
        message.reply_text = AsyncMock()
        update = SimpleNamespace(effective_chat=chat, effective_message=message)
        with patch("telegram_bot.bot_handler.parse_assistance_link_payload") as parse, \
                patch("telegram_bot.bot_handler.find_request_by_reference") as find, \
                patch("telegram_bot.bot_handler.link_chat_to_request") as link, \
                patch("telegram_bot.bot_handler.unlink_chat_requests") as remove:
            for handler in (start, handle_message, unlink):
                async_to_sync(handler)(update, None)
            parse.assert_not_called()
            find.assert_not_called()
            link.assert_not_called()
            remove.assert_not_called()
        message.reply_text.assert_not_awaited()

    def test_group_chat_is_rejected_before_credential_handling(self):
        self.assert_chat_rejected(SimpleNamespace(id=-100, type="group"))

    def test_supergroup_chat_is_rejected_before_credential_handling(self):
        self.assert_chat_rejected(SimpleNamespace(id=-100, type="supergroup"))

    def test_channel_is_rejected_before_credential_handling(self):
        self.assert_chat_rejected(SimpleNamespace(id=-100, type="channel"))

    def test_missing_or_unexpected_chat_metadata_fails_closed(self):
        for chat in (None, SimpleNamespace(), SimpleNamespace(id=123),
                     SimpleNamespace(id=123, type=None), SimpleNamespace(id=123, type="unknown"),
                     SimpleNamespace(id=-1, type="private"), SimpleNamespace(id=True, type="private"),
                     SimpleNamespace(id="123", type="private")):
            with self.subTest(chat=chat):
                self.assert_chat_rejected(chat)

    def test_missing_update_or_message_fails_closed(self):
        for update in (None, SimpleNamespace(), SimpleNamespace(
                effective_chat=SimpleNamespace(id=123, type="private"), effective_message=None)):
            for handler in (start, handle_message, unlink):
                async_to_sync(handler)(update, None)


class PrivateChatBindingTests(TestCase):
    def setUp(self):
        kind = AssistanceType.objects.create(name="Synthetic private-chat program")
        self.req = AssistanceRequest.objects.create(reference_code="PRIVATE-CHAT", assistance_type=kind,
            full_name="Private Citizen Sentinel", email="private@example.test", phone="09123456789")
        self.token = self.req.secure_edit_token

    def test_private_binding_persists_only_current_authorized_association(self):
        linked = link_chat_to_request(self.req, 123, chat_type="private", access_token=self.token)
        self.req.refresh_from_db()
        self.assertEqual(linked.pk, self.req.pk)
        self.assertEqual(self.req.telegram_chat_id, "123")
        self.assertEqual(self.req.status, "submitted")

    def test_non_private_binding_cannot_bypass_handler_or_touch_authorization(self):
        with patch("telegram_bot.services.message_service.locked_request_for_mutation") as lock:
            for chat_type in ("group", "supergroup", "channel", None, "unknown"):
                with self.subTest(chat_type=chat_type), self.assertRaises(ValueError):
                    link_chat_to_request(self.req, 123, chat_type=chat_type, access_token=self.token)
            lock.assert_not_called()
        self.req.refresh_from_db()
        self.assertIsNone(self.req.telegram_chat_id)

    def test_credential_revocation_and_claim_are_rechecked_before_binding(self):
        AssistanceRequest.objects.filter(pk=self.req.pk).update(edit_code="111111")
        with self.assertRaises(Http404):
            link_chat_to_request(self.req, 123, chat_type="private", access_token=self.token)
        self.req.refresh_from_db()
        self.token = self.req.secure_edit_token
        AssistanceRequest.objects.filter(pk=self.req.pk).update(claimed_at=timezone.now())
        with self.assertRaises(ValueError):
            link_chat_to_request(self.req, 123, chat_type="private", access_token=self.token)
        self.req.refresh_from_db()
        self.assertIsNone(self.req.telegram_chat_id)
