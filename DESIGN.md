# DESIGN.md - twilist-rss

## 1. Overview

twilist-rss fetches a private X (formerly Twitter) list on a schedule, filters to normal posts only, generates an RSS 2.0 feed, and uploads it to S3 (static website hosting). Slack consumes the feed URL through the Slack RSS app and posts updates into a channel.

This project intentionally follows a "subtractive" design: keep responsibilities minimal.

- Fetch: twscrape (Python)
- Publish: S3 (boto3)
- Delivery: Slack RSS app (delegated to Slack)
- State: basically stateless (rely on RSS GUID dedup behavior)

## 2. Goals / Non-goals

### Goals
- Fetch timeline-equivalent data from a private list and publish only normal posts as RSS.
- Generate stable RSS 2.0 that is consumable by the Slack RSS app.
- Keep dependencies local to the project directory (uv/lock) on a workstation.
- Even on failure, publish one observable error item in RSS.

### Non-goals
- Real-time delivery (sub-minute cadence).
- High availability (always-on redundancy).
- Implementation based on the official X API.
- Direct Slack posting (webhooks, bots, etc.); delegated to Slack RSS app.
- Media enclosure support for images/videos; delegated to Slack link previews.

## 3. Overall Architecture

### Data flow
1. Inject cookie-based auth data into twscrape account context.
2. Fetch list timeline entries (upper bound is several times feed size).
3. Filter out replies / reposts / quotes.
4. Generate RSS 2.0 (latest 50 by default).
5. Overwrite a target S3 key via boto3 PUT.
6. Slack RSS app polls and posts to Slack.

### Expected schedule
- Fixed JST times: 05:00 / 11:00 / 17:00 / 23:00
- Start with manual runs for validation, then move to systemd user timer.

## 4. Implementation Policy (Subtractive)

- Assume one list to one feed.
- Do not persist state. Deduplicate via stable RSS GUID (`tweet_id`).
- On failure, update the feed with exactly one error item.
- Do not process media in-app (text + URL is enough).

## 5. List Input Constraints

- Accept only `https://x.com/i/lists/<list_id>` format.
- Extract `<list_id>` via regex and pass it to the fetch API.
- Other forms (`owner/slug`, etc.) are out of initial scope.

## 6. Post Filtering Rules (Normal Posts Only)

A post is included only if all conditions hold:

- Not a reply (`inReplyToTweetId` is absent)
- Not a repost (`retweetedTweet` is absent)
- Not a quote (`quotedTweet` is absent)

Implementation uses `getattr` to tolerate twscrape model changes. Missing fields are treated as "not excluded".

## 7. RSS Specification (RSS 2.0)

- Format: RSS 2.0
- Feed size: latest 50 items
- Time zone: UTC for `pubDate`, `lastBuildDate`, and error timestamps

### Channel fields
- `title`: env `FEED_TITLE` (default: `X List Feed`)
- `link`: `X_LIST_URL` (for example, `https://x.com/i/lists/<list_id>`)
- `description`: env `FEED_DESCRIPTION` (default: `X list timeline feed`)
- `lastBuildDate`: generation time in UTC (RFC822)

### Item fields
- `guid`: stable `tweet_id` (`isPermaLink="false"`)
- `title`: `@{username}: {first 50 chars of text}` with trailing `…` when truncated
- `description`: HTML wrapped by CDATA
  ```html
  <p>full text</p><p><a href="tweet URL">tweet URL</a></p>
  ```
- `link`: tweet URL (`https://x.com/{username}/status/{tweet_id}`)
- `pubDate`: tweet time in UTC (RFC822)

### Error item (single item on failure)
- `title`: `X list fetch failed`
- `link`: list URL (`X_LIST_URL`)
- `guid`: `error-{epoch_seconds}` (UTC unix seconds)
- `description`: HTML in CDATA: `<p>{ExceptionType}: {message}</p><p>generated-at UTC</p>`
- It is acceptable for Slack to receive this item (observability first).

## 8. S3 Publishing Specification

- Exposure: S3 static website hosting
- Object key: prefixed path (for example, `feeds/x/list.xml`)
- PUT params:
  - `ContentType`: `application/rss+xml; charset=utf-8`
  - `CacheControl`: short TTL recommended (for example, `max-age=300`)
- ACL: not set in code (public access handled by bucket policy and operations)

## 9. Runtime and Dependency Management

- Language: Python
- Dependency manager: uv (`pyproject.toml` + `uv.lock`)
- Python requirement: >= 3.11
- Entry point: `./run` wrapper executes `uv run python -m twilist_rss`
- Logging: plain stdout

### Recommended directory layout

```text
twilist-rss/
pyproject.toml
uv.lock
run
setup
.env               # local only (not committed)
.env.example
src/
  twilist_rss/
    __init__.py
    __main__.py
    config.py
    job.py
    rss.py
    publish.py
```

## 10. Configuration (.env / Environment Variables)

If `.env` exists, load from it. Otherwise read from environment variables.

### Required
- `X_LIST_URL`: `https://x.com/i/lists/<list_id>`
- `X_USERNAME`: X account username (used as twscrape account identifier)
- `X_COOKIE`: cookie header string from browser requests
- `S3_BUCKET`: destination bucket
- `S3_KEY`: destination key (for example, `feeds/x/list.xml`)

### Optional (defaults apply)
- `FEED_TITLE`: default `X List Feed`
- `FEED_DESCRIPTION`: default `X list timeline feed`
- `MAX_ITEMS`: default `50`
- `FETCH_MULT`: default `5`
- `TWS_DB_PATH`: default `.data/twscrape.db`
- `AWS_REGION`: optional (boto3 default chain if omitted)
- `AWS_PROFILE`: optional

## 11. Cookie Operation Policy

### Injection strategy
- On every run, call `AccountsPool.add_account` and overwrite account cookies from `X_COOKIE`.
- Use `X_USERNAME` as the twscrape account key.
- Always source cookies from `X_COOKIE` env value.
- Use twscrape DB (`TWS_DB_PATH`) for session plumbing only, not as cookie truth.

### Capture and rotation
- Initial setup: paste full browser cookie header into `X_COOKIE` and make it work first.
- After stabilization: optionally trim unnecessary cookie keys while keeping required auth keys.
- Refresh trigger: repeated fetch failures suggest expiration; recapture and update `.env`.

(Cookie capture steps are out of design scope.)

## 12. Error Handling and Observability

- Do not swallow exceptions.
- On failure, publish an RSS feed containing one error item and allow Slack visibility.
- Emit `[INFO]` / `[ERROR]` logs to stdout for post-mortem analysis.
- If normal config loading fails, attempt an error-feed publish using fallback env values when possible.

## 13. Compatibility and Change Tolerance

- Use `getattr` in filtering logic to tolerate twscrape schema changes.
- Keep URL/ID generation anchored to `tweet_id` for stable GUID behavior.
- Keep dependency updates reproducible with `uv lock` / `uv sync`.

## 14. Minimal Development/Run Flow

- First time:
  - `./setup`
  - Copy `.env.example` to `.env` and fill values
  - Run `./run` manually
- After stabilization:
  - Run `./run` from a systemd user timer at fixed JST times

## 15. Possible Future Extensions

- Multi-list support (multiple feeds)
- Separate channel strategy for failure notifications
- Fetch fallback strategies when list fetch is unavailable
- Atom feed generation if needed

