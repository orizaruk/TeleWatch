"""Regression checks for Telegram links in ntfy alerts; no external sends."""

import asyncio
import contextlib
import io
import json
import logging
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from telethon.tl.types import Message, MessageEntityTextUrl, MessageEntityUrl, PeerChannel

import main
from notifiers.ntfy import NtfyNotifier, format_telegram_links


AMAZON_URL = 'https://amazon.jobs/en/jobs/10551577/software-development-student-agi-ds'
MOBILEYE_URL = 'https://jobs.eu.lever.co/mobileye/568f4a72-8cd2-4c33-9d09-1a62e21dacc7'


def telegram_message(text, anchors=(), visible_urls=()):
    entities = []
    for label, url in anchors:
        offset = len(text[:text.index(label)].encode('utf-16-le')) // 2
        length = len(label.encode('utf-16-le')) // 2
        entities.append(MessageEntityTextUrl(offset, length, url))
    for url in visible_urls:
        offset = len(text[:text.index(url)].encode('utf-16-le')) // 2
        length = len(url.encode('utf-16-le')) // 2
        entities.append(MessageEntityUrl(offset, length))
    return Message(id=33023, peer_id=PeerChannel(2297490495), message=text,
                   entities=sorted(entities, key=lambda entity: entity.offset))


class FormatLinksTests(unittest.TestCase):
    def test_todays_amazon_and_mobileye_application_links(self):
        for title, location, url in (
            ('Software Development Student, AGI-DS @ Amazon', 'Haifa, ISR, Tel Aviv, ISR, Tel-aviv, ISR', AMAZON_URL),
            ('Data Analysis Engineer - Student Position @ Mobileye', 'Jerusalem, Israel', MOBILEYE_URL),
        ):
            with self.subTest(title=title):
                text = f'{title}\nLocation: {location}\nClick here to apply now!\n#StudentJob'
                message = telegram_message(text, [('Click here to apply now!', url)])
                body, click = format_telegram_links(text, message)
                self.assertIn(f'Click here to apply now!: {url}', body)
                self.assertTrue(body.startswith(text))
                self.assertEqual(click, url)

    def test_emoji_offsets_and_multiple_links_prefer_application(self):
        text = '🔥 Student job — חברה\nCompany website\nApply now 🚀'
        message = telegram_message(text, [
            ('Company website', 'https://example.com'),
            ('Apply now 🚀', AMAZON_URL),
        ])
        body, click = format_telegram_links(text, message)
        self.assertIn('Company website: https://example.com', body)
        self.assertIn(f'Apply now 🚀: {AMAZON_URL}', body)
        self.assertEqual(click, AMAZON_URL)

    def test_visible_and_repeated_links_are_not_duplicated(self):
        text = f'🔥 Student job\n{AMAZON_URL}\nApply now\nMore details'
        message = telegram_message(text, [
            ('Apply now', AMAZON_URL), ('More details', AMAZON_URL),
        ], [AMAZON_URL])
        body, click = format_telegram_links(text, message)
        self.assertEqual(body, text)
        self.assertEqual(click, AMAZON_URL)

        text = 'Student job\nApply now\nMore details'
        message = telegram_message(text, [('Apply now', AMAZON_URL), ('More details', AMAZON_URL)])
        body, click = format_telegram_links(text, message)
        self.assertEqual(body.count(AMAZON_URL), 1)
        self.assertEqual(click, AMAZON_URL)

    def test_plain_message_and_non_web_links(self):
        self.assertEqual(format_telegram_links('Student job'), ('Student job', None))
        for url in ('mailto:jobs@example.com', 'javascript:alert(1)', 'https://[invalid', 'https://example.com/\nextra'):
            with self.subTest(url=url):
                message = telegram_message('Student job\nApply', [('Apply', url)])
                self.assertEqual(format_telegram_links(message.message, message), (message.message, None))


class NtfyDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_unicode_json_payload_contains_application_url_and_click(self):
        text = '🔥 Student job\nApply now'
        message = telegram_message(text, [('Apply now', AMAZON_URL)])
        with patch('notifiers.ntfy.urllib.request.urlopen') as urlopen:
            success = await NtfyNotifier().send(text, 'משרות 🔔', ['student'], 'test-topic', message)
        self.assertTrue(success)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, 'https://ntfy.sh/')
        payload = json.loads(request.data)
        self.assertEqual(payload['topic'], 'test-topic')
        self.assertEqual(payload['title'], 'Job Alert [משרות 🔔]')
        self.assertIn(AMAZON_URL, payload['message'])
        self.assertEqual(payload['click'], AMAZON_URL)
        urlopen.return_value.__exit__.assert_called_once()

    async def test_existing_plain_text_test_notification_still_works(self):
        with patch('notifiers.ntfy.urllib.request.urlopen') as urlopen:
            success = await NtfyNotifier().send('Test notification', 'Test', ['test'], 'test-topic')
        self.assertTrue(success)
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(payload['message'], 'Keywords: test\n\nTest notification')
        self.assertNotIn('click', payload)

    async def test_monitor_passes_original_message_to_ntfy(self):
        ready = asyncio.Event()
        handlers = []
        def on(builder):
            def register(handler):
                handlers.append(handler)
                ready.set()
                return handler
            return register
        client = SimpleNamespace(on=on, remove_event_handler=MagicMock())
        config = {
            'chats': [2297490495], 'keywords': ['student'],
            'excluded_keywords': ['marketing', 'community', 'HR'],
            'destinations': {'ntfy': {'enabled': True, 'topic': 'test-topic'}},
        }
        text = 'Software Development Student, AGI-DS @ Amazon\nLocation: Haifa, Tel Aviv\nApply now'
        message = telegram_message(text, [('Apply now', AMAZON_URL)])
        event = SimpleNamespace(message=message, id=33023, chat_id=-1002297490495,
                                get_chat=AsyncMock(return_value=SimpleNamespace(title='Tech Job Tracker IL')))
        with patch.object(main, 'config', config, create=True), \
             patch.object(main, 'logger', logging.getLogger('ntfy-tests')), \
             patch.object(main, 'health_monitor', new=AsyncMock()), \
             patch.dict(main.stats, clear=True), \
             patch('notifiers.ntfy.urllib.request.urlopen') as urlopen, \
             contextlib.redirect_stdout(io.StringIO()):
            task = asyncio.create_task(main.run_bot(client, exit_on_stop=True))
            try:
                await asyncio.wait_for(ready.wait(), timeout=2)
                await handlers[0](event)
                payload = json.loads(urlopen.call_args.args[0].data)
                self.assertIn(AMAZON_URL, payload['message'])
                self.assertEqual(payload['click'], AMAZON_URL)
                self.assertEqual(main.stats['notifications_sent'], 1)
                self.assertEqual(main.stats['notifications_failed'], 0)
            finally:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task


if __name__ == '__main__':
    unittest.main()
