import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


_ENV_PATH = Path('.env')
if _ENV_PATH.exists():
    load_dotenv(dotenv_path=_ENV_PATH)


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value == '':
        raise ValueError(
            f'Missing required environment variable: {name}',
        )
    return value


def _get_env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None or value == '':
        return default
    return value


def _get_env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value == '':
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(
            f'Environment variable {name} must be an integer',
        ) from exc


def _get_env_optional(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None or value == '':
        return None
    return value


@dataclass
class Config:
    x_list_url: str
    x_username: str
    x_cookie: str
    s3_bucket: str
    s3_key: str

    feed_title: str = 'X List Feed'
    feed_description: str = 'X list timeline feed'
    max_items: int = 50
    fetch_mult: int = 5
    tws_db_path: str = '.data/twscrape.db'
    aws_region: str | None = None
    aws_profile: str | None = None
    validate_list_url: bool = True

    list_id: str = field(init=False)

    def __post_init__(self) -> None:
        match = re.search(r'/lists/(\d+)', self.x_list_url)
        if match is None and self.validate_list_url:
            raise ValueError(
                'X_LIST_URL must include a list id like /lists/1234567890',
            )
        self.list_id = match.group(1) if match is not None else '0'


def load_config() -> Config:
    return Config(
        x_list_url=_require_env('X_LIST_URL'),
        x_username=_require_env('X_USERNAME'),
        x_cookie=_require_env('X_COOKIE'),
        s3_bucket=_require_env('S3_BUCKET'),
        s3_key=_require_env('S3_KEY'),
        feed_title=_get_env_str('FEED_TITLE', 'X List Feed'),
        feed_description=_get_env_str(
            'FEED_DESCRIPTION',
            'X list timeline feed',
        ),
        max_items=_get_env_int('MAX_ITEMS', 50),
        fetch_mult=_get_env_int('FETCH_MULT', 5),
        tws_db_path=_get_env_str('TWS_DB_PATH', '.data/twscrape.db'),
        aws_region=_get_env_optional('AWS_REGION'),
        aws_profile=_get_env_optional('AWS_PROFILE'),
    )


def load_error_config() -> Config | None:
    s3_bucket = _get_env_optional('S3_BUCKET')
    s3_key = _get_env_optional('S3_KEY')
    if s3_bucket is None or s3_key is None:
        return None

    x_list_url = _get_env_optional('X_LIST_URL') or 'https://x.com/i/lists/0'

    return Config(
        x_list_url=x_list_url,
        x_username=_get_env_optional('X_USERNAME') or '<unknown>',
        x_cookie='',
        s3_bucket=s3_bucket,
        s3_key=s3_key,
        feed_title=_get_env_str('FEED_TITLE', 'X List Feed'),
        feed_description=_get_env_str(
            'FEED_DESCRIPTION',
            'X list timeline feed',
        ),
        max_items=1,
        fetch_mult=1,
        tws_db_path=_get_env_str('TWS_DB_PATH', '.data/twscrape.db'),
        aws_region=_get_env_optional('AWS_REGION'),
        aws_profile=_get_env_optional('AWS_PROFILE'),
        validate_list_url=False,
    )
