import asyncio
import sys

from .config import load_config, load_error_config
from .job import fetch_tweets
from .publish import publish
from .rss import build_error_feed, build_feed


def main() -> None:
    config = None
    try:
        config = load_config()
        print(f'[INFO] Fetching list {config.list_id} ...')
        tweets = asyncio.run(fetch_tweets(config))
        print(f'[INFO] Fetched {len(tweets)} normal posts')
        xml = build_feed(tweets, config)
        print(
            f'[INFO] Publishing to s3://{config.s3_bucket}/'
            f'{config.s3_key}',
        )
        publish(xml, config)
        print('[INFO] Done')
    except Exception as exc:
        print(f'[ERROR] {type(exc).__name__}: {exc}')
        error_config = config or load_error_config()
        if error_config is not None:
            xml = build_error_feed(exc, error_config)
            publish(xml, error_config)
            print('[ERROR] Error feed published')
        else:
            print('[ERROR] Insufficient env vars for error-feed publish')
        sys.exit(1)


if __name__ == '__main__':
    main()
