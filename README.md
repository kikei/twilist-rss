# twilist-rss

A tool that fetches a private X (formerly Twitter) list on a schedule, keeps only normal posts, generates an RSS 2.0 feed, and publishes it to S3. It is designed to be consumed by the Slack RSS app.

See [DESIGN.md](./DESIGN.md) for the detailed design.

## Setup

```bash
cp .env.example .env
# Edit .env and fill required variables
./setup      # uv sync + twscrape patch
```

## Configuration (.env)

| Variable | Required | Description |
|---|---|---|
| `X_LIST_URL` | ✅ | `https://x.com/i/lists/<list_id>` |
| `X_USERNAME` | ✅ | X account username |
| `X_COOKIE` | ✅ | Cookie header string captured from browser requests |
| `S3_BUCKET` | ✅ | Destination S3 bucket name |
| `S3_KEY` | ✅ | Destination S3 object key (example: `feeds/x/list.xml`) |
| `FEED_TITLE` | — | RSS channel title (default: `X List Feed`) |
| `FEED_DESCRIPTION` | — | RSS channel description |
| `MAX_ITEMS` | — | Max items in feed (default: 50) |
| `FETCH_MULT` | — | Fetch multiplier (default: 5, to offset filtered items) |
| `TWS_DB_PATH` | — | twscrape DB path (default: `.data/twscrape.db`) |
| `AWS_REGION` | — | AWS region |
| `AWS_PROFILE` | — | AWS CLI profile name |

### X_COOKIE

Capture the cookie header value from a request to the `ListLatestTweetsTimeline` endpoint.

```dotenv
X_COOKIE='auth_token=xxx; ct0=yyy; ...'
```

Use single quotes. Double quotes can break dotenv parsing.

The cookie is injected into twscrape on each run. If repeated fetch failures indicate expiration, capture a fresh cookie value in the browser and update `.env`.

## Run

```bash
./run
```

On failure, the tool writes an RSS feed containing one error item to S3 (visible in Slack). If startup config cannot be fully loaded, it still attempts to publish the error feed as long as `S3_BUCKET` and `S3_KEY` are available.

## Scheduled Run (systemd timer)

```ini
# ~/.config/systemd/user/twilist-rss.service
[Unit]
Description=twilist-rss feed generator

[Service]
Type=oneshot
WorkingDirectory=/path/to/twilist-rss
ExecStart=/path/to/twilist-rss/run
```

```ini
# ~/.config/systemd/user/twilist-rss.timer
[Unit]
Description=twilist-rss timer

[Timer]
OnCalendar=*-*-* 05,11,17,23:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemctl --user enable --now twilist-rss.timer
```

---

## About the twscrape Patch

`./setup` runs `uv sync` and then patches `xclid.py` in the installed twscrape package.

### Background

twscrape 0.17.0 fetches `https://x.com/tesla` before API requests and parses a webpack bundle map to generate `x-client-transaction-id` tokens.

That bundle map is a JavaScript object literal. Most keys are quoted strings, but some keys (such as `node_modules_pnpm_...`) are unquoted JavaScript identifiers. twscrape attempts to parse the map with `json.loads()`, but JSON does not allow unquoted keys, which causes `JSONDecodeError` and then `Failed to parse scripts`, breaking all requests.

### Patch Details

`json.loads()` inside `get_scripts_list()` is replaced with regex extraction of quoted key-value pairs only (`re.finditer`).

```python
# Before
for k, v in json.loads(scripts).items():
    yield script_url(k, f"{v}a")

# After
for m in re.finditer(r'"([^"]+)"\s*:\s*"([^"]+)"', scripts):
    yield script_url(m.group(1), f"{m.group(2)}a")
```

Only quoted keys (for example, `"ondemand.s.xxxxxxx":"hash"`) are required for this flow, so skipping unquoted keys does not break functionality.

### If the Patch Disappears

Running `uv sync` can overwrite the patch. Re-apply it by running `./setup`.

If twscrape is upgraded beyond 0.17.0, `./setup` may print `patch target not found`. In that case, inspect twscrape's `xclid.py` and verify whether the patch is still needed or requires an update.
