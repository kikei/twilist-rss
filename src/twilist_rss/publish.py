import boto3

from .config import Config


def publish(xml: str, config: Config) -> None:
    session_kwargs: dict[str, str] = {}

    if config.aws_profile is not None:
        session_kwargs['profile_name'] = config.aws_profile
    if config.aws_region is not None:
        session_kwargs['region_name'] = config.aws_region

    session = boto3.Session(**session_kwargs)
    s3 = session.client('s3')

    s3.put_object(
        Bucket=config.s3_bucket,
        Key=config.s3_key,
        Body=xml.encode('utf-8'),
        ContentType='application/rss+xml; charset=utf-8',
        CacheControl='max-age=300',
    )
