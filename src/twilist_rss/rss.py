from datetime import datetime, timezone
import html
import re
from xml.etree import ElementTree as ET

from .config import Config


_COOKIE_PATTERN = re.compile(
    r'(auth_token|ct0|twid|guest_id|kdt|att)'
    r'=[^\s;,\'"&]+',
    re.IGNORECASE,
)


def _sanitize_exc(exc: Exception) -> str:
    """Redact cookie values and cap message length to 200 characters."""
    msg = _COOKIE_PATTERN.sub(r'\1=<redacted>', str(exc))
    if len(msg) > 200:
        msg = msg[:200] + '…'
    return f'{type(exc).__name__}: {msg}'


_RFC822_FMT = '%a, %d %b %Y %H:%M:%S +0000'


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _format_rfc822_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.strftime(_RFC822_FMT)


def _build_base_feed(config: Config) -> tuple[ET.Element, ET.Element]:
    rss = ET.Element('rss', {'version': '2.0'})
    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text = config.feed_title
    ET.SubElement(channel, 'link').text = config.x_list_url
    ET.SubElement(channel, 'description').text = config.feed_description
    ET.SubElement(channel, 'lastBuildDate').text = _format_rfc822_utc(
        _now_utc(),
    )
    return rss, channel


def _wrap_cdata(value: str) -> str:
    safe_value = value.replace(']]>', ']]]]><![CDATA[>')
    return f'<![CDATA[{safe_value}]]>'


def _set_cdata(
    element: ET.Element,
    value: str,
    cdata_map: dict[str, str],
    index: int,
) -> None:
    token = f'__TWILIST_CDATA_{index}__'
    element.text = token
    cdata_map[token] = _wrap_cdata(value)


def _render_xml(root: ET.Element, cdata_map: dict[str, str]) -> str:
    xml = ET.tostring(
        root,
        encoding='utf-8',
        xml_declaration=True,
    ).decode('utf-8')
    for token, cdata_value in cdata_map.items():
        xml = xml.replace(token, cdata_value)
    return xml


def _tweet_username(tweet: object) -> str:
    user = getattr(tweet, 'user', None)
    username = getattr(user, 'username', '')
    if username is None:
        return ''
    return str(username)


def _tweet_id(tweet: object) -> str:
    tweet_id = getattr(tweet, 'id', '')
    if tweet_id is None:
        return ''
    return str(tweet_id)


def _tweet_text(tweet: object) -> str:
    text = getattr(tweet, 'rawContent', '')
    if text is None:
        return ''
    return str(text)


def _tweet_url(tweet: object) -> str:
    username = _tweet_username(tweet)
    tweet_id = _tweet_id(tweet)
    return f'https://x.com/{username}/status/{tweet_id}'


def _tweet_pub_date(tweet: object) -> str:
    value = getattr(tweet, 'date', None)
    if isinstance(value, datetime):
        return _format_rfc822_utc(value)
    return _format_rfc822_utc(_now_utc())


def _tweet_title(tweet: object) -> str:
    username = _tweet_username(tweet)
    text = _tweet_text(tweet)
    preview = f'{text[:50]}…' if len(text) > 50 else text
    return f'@{username}: {preview}'


def build_feed(tweets: list, config: Config) -> str:
    rss, channel = _build_base_feed(config)
    cdata_map: dict[str, str] = {}
    cdata_index = 0

    for tweet in tweets:
        item = ET.SubElement(channel, 'item')
        tweet_id = _tweet_id(tweet)
        url = _tweet_url(tweet)
        text = _tweet_text(tweet)
        escaped_text = html.escape(text)
        escaped_url_text = html.escape(url)

        guid = ET.SubElement(item, 'guid', {'isPermaLink': 'false'})
        guid.text = tweet_id
        ET.SubElement(item, 'title').text = _tweet_title(tweet)

        description = ET.SubElement(item, 'description')
        description_html = (
            f'<p>{escaped_text}</p>'
            f'<p><a href="{url}">{escaped_url_text}</a></p>'
        )
        _set_cdata(
            description,
            description_html,
            cdata_map,
            cdata_index,
        )
        cdata_index += 1

        ET.SubElement(item, 'link').text = url
        ET.SubElement(item, 'pubDate').text = _tweet_pub_date(tweet)

    return _render_xml(rss, cdata_map)


def build_error_feed(exc: Exception, config: Config) -> str:
    rss, channel = _build_base_feed(config)
    cdata_map: dict[str, str] = {}
    now = _now_utc()

    item = ET.SubElement(channel, 'item')
    ET.SubElement(item, 'title').text = 'X list fetch failed'
    ET.SubElement(item, 'link').text = config.x_list_url

    guid = ET.SubElement(item, 'guid', {'isPermaLink': 'false'})
    guid.text = f'error-{int(now.timestamp())}'

    description = ET.SubElement(item, 'description')
    escaped_error = html.escape(_sanitize_exc(exc))
    description_html = (
        f'<p>{escaped_error}</p>'
        f'<p>{now.isoformat()} UTC</p>'
    )
    _set_cdata(
        description,
        description_html,
        cdata_map,
        0,
    )

    return _render_xml(rss, cdata_map)
