from pathlib import Path

import twscrape

from .config import Config


def _is_normal_post(tweet: object) -> bool:
    return (
        not getattr(tweet, 'inReplyToTweetId', None)
        and not getattr(tweet, 'retweetedTweet', None)
        and not getattr(tweet, 'quotedTweet', None)
    )


async def fetch_tweets(config: Config) -> list:
    db_path = Path(config.tws_db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    api = twscrape.API(config.tws_db_path)
    await api.pool.delete_accounts(config.x_username)
    await api.pool.add_account(
        config.x_username,
        password='',
        email='',
        email_password='',
        cookies=config.x_cookie,
    )

    if config.max_items < 1:
        raise ValueError('MAX_ITEMS must be >= 1')
    if config.fetch_mult < 1:
        raise ValueError('FETCH_MULT must be >= 1')
    fetch_count = config.max_items * config.fetch_mult

    tweets = []
    async for tweet in api.list_timeline(config.list_id, limit=fetch_count):
        tweets.append(tweet)

    filtered = [tweet for tweet in tweets if _is_normal_post(tweet)]
    return filtered[: config.max_items]
