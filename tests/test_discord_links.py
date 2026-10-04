"""Regression checks for Telegram links in Discord alerts; no external sends."""

import json
import unittest
from unittest.mock import patch

from notifiers.discord import DiscordNotifier
from notifiers.links import to_discord_markdown
from tests.test_ntfy_links import AMAZON_URL, MOBILEYE_URL, telegram_message


class DiscordMarkdownTests(unittest.TestCase):
    def test_hidden_apply_link_becomes_masked_link(self):
        text = 'Data Analysis Engineer - Student Position @ Mobileye\nLocation: Jerusalem\nClick here to apply now!\n#StudentJob'
        message = telegram_message(text, [('Click here to apply now!', MOBILEYE_URL)])
        self.assertEqual(
            to_discord_markdown(text, message),
            text.replace('Click here to apply now!', f'[Click here to apply now!]({MOBILEYE_URL})'),
        )

    def test_emoji_offsets_multiple_links_and_markdown_in_label(self):
        text = '🔥 Student job — חברה\nCompany_site [new]\nApply now 🚀'
        message = telegram_message(text, [
            ('Company_site [new]', 'https://example.com/a_(b)'),
            ('Apply now 🚀', AMAZON_URL),
        ])
        self.assertEqual(
            to_discord_markdown(text, message),
            '🔥 Student job — חברה\n'
            '[Company\\_site \\[new\\]](https://example.com/a_(b%29)\n'
            f'[Apply now 🚀]({AMAZON_URL})',
        )

    def test_plain_visible_and_unsafe_links_unchanged(self):
        self.assertEqual(to_discord_markdown('Student job'), 'Student job')
        text = f'Student job\n{AMAZON_URL}\nApply'
        message = telegram_message(text, [('Apply', 'javascript:alert(1)')], [AMAZON_URL])
        self.assertEqual(to_discord_markdown(text, message), text)


class DiscordDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_payload_has_clickable_description_and_title(self):
        text = 'Software Development Student @ Amazon\nClick here to apply now!'
        message = telegram_message(text, [('Click here to apply now!', AMAZON_URL)])
        with patch('notifiers.discord.urllib.request.urlopen') as urlopen:
            success = await DiscordNotifier().send(
                text, 'Tech Job Tracker IL', ['student'], 'https://discord.test/hook', message)
        self.assertTrue(success)
        embed = json.loads(urlopen.call_args.args[0].data)['embeds'][0]
        self.assertIn(f'[Click here to apply now!]({AMAZON_URL})', embed['description'])
        self.assertEqual(embed['url'], AMAZON_URL)

    async def test_plain_test_notification_has_no_url(self):
        with patch('notifiers.discord.urllib.request.urlopen') as urlopen:
            success = await DiscordNotifier().send('Test', 'Test', ['test'], 'https://discord.test/hook')
        self.assertTrue(success)
        embed = json.loads(urlopen.call_args.args[0].data)['embeds'][0]
        self.assertEqual(embed['description'], 'Test')
        self.assertNotIn('url', embed)


if __name__ == '__main__':
    unittest.main()
