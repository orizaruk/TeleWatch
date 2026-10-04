"""Helpers for recovering web links that Telegram stores as message entities."""

import re
import urllib.parse
from telethon.helpers import add_surrogate, del_surrogate
from telethon.tl.types import MessageEntityTextUrl, MessageEntityUrl

_DISCORD_LABEL_SPECIALS = re.compile(r'([\\\[\]()*_~`|>])')


def is_safe_web_url(url: str) -> bool:
    """
    Check whether a URL is an http(s) link that is safe to put in a notification.

    Args:
        url: Candidate URL taken from a Telegram entity

    Returns:
        True for well-formed http/https URLs without whitespace or control characters
    """
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        return False
    return not any(character.isspace() or ord(character) < 32 for character in url)


def extract_web_links(telegram_message) -> list[tuple[str, str, bool]]:
    """
    List the web links in a Telegram message, both visible and hidden behind text.

    Args:
        telegram_message: Telethon Message (or None)

    Returns:
        (label, url, embedded) tuples in message order; embedded is True when the
        URL is hidden behind link text such as "Click here to apply now!"
    """
    if telegram_message is None:
        return []

    links = []
    # Telethon handles Telegram's UTF-16 offsets, including text containing emoji.
    for entity, label in telegram_message.get_entities_text():
        if isinstance(entity, MessageEntityTextUrl):
            url, embedded = entity.url, True
        elif isinstance(entity, MessageEntityUrl):
            url, embedded = label, False
        else:
            continue
        if is_safe_web_url(url):
            links.append((label, url, embedded))
    return links


def pick_click_url(links: list[tuple[str, str, bool]]) -> str | None:
    """
    Choose the link a notification tap/title should open.

    Args:
        links: Output of extract_web_links

    Returns:
        The first link whose label mentions "apply", else the first link, else None
    """
    if not links:
        return None
    # Prefer an application link over a company homepage elsewhere in the post.
    return next(
        (url for label, url, _ in links if 'apply' in label.casefold()),
        links[0][1],
    )


def to_discord_markdown(message: str, telegram_message=None) -> str:
    """
    Turn Telegram's hidden text links into Discord masked links.

    Example: "Click here to apply now!" linked to https://x.co/job becomes
    "[Click here to apply now!](https://x.co/job)".

    Args:
        message: Plain message text
        telegram_message: Original Telethon Message carrying link entities

    Returns:
        The message with embedded links rendered as Discord markdown
    """
    if telegram_message is None or not telegram_message.entities:
        return message

    # Entity offsets count UTF-16 code units, so work on the surrogate-expanded text.
    text = add_surrogate(message)
    text_links = sorted(
        (entity for entity in telegram_message.entities
         if isinstance(entity, MessageEntityTextUrl) and is_safe_web_url(entity.url)),
        key=lambda entity: entity.offset,
        reverse=True,  # Replace from the end so earlier offsets stay valid.
    )
    for entity in text_links:
        start, end = entity.offset, entity.offset + entity.length
        label = text[start:end]
        # Keep surrounding whitespace outside the brackets so Discord parses the link.
        stripped = label.strip()
        if not stripped:
            continue
        lead = label[:len(label) - len(label.lstrip())]
        trail = label[len(label.rstrip()):]
        escaped = _DISCORD_LABEL_SPECIALS.sub(r'\\\1', stripped)
        url = entity.url.replace(')', '%29')
        text = f"{text[:start]}{lead}[{escaped}]({url}){trail}{text[end:]}"
    return del_surrogate(text)
