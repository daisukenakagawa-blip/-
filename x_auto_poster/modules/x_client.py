"""X (Twitter) への投稿。tweepy 経由で OAuth 1.0a User Context を使う。

- 本文の投稿: API v2 (POST /2/tweets)
- 画像のアップロード: API v1.1 (media/upload)
"""

import config
from modules.logger import get_logger, log_error

logger_ = None


def _log():
    global logger_
    if logger_ is None:
        logger_ = get_logger()
    return logger_


def _clients():
    """(v2 Client, v1.1 API) のタプルを返す。"""
    import tweepy

    if not config.x_credentials_ready():
        raise RuntimeError(
            "X API の認証情報が未設定です。.env の X_API_KEY / X_API_SECRET / "
            "X_ACCESS_TOKEN / X_ACCESS_TOKEN_SECRET を設定してください。"
        )

    client = tweepy.Client(
        consumer_key=config.X_API_KEY,
        consumer_secret=config.X_API_SECRET,
        access_token=config.X_ACCESS_TOKEN,
        access_token_secret=config.X_ACCESS_TOKEN_SECRET,
    )
    auth = tweepy.OAuth1UserHandler(
        config.X_API_KEY,
        config.X_API_SECRET,
        config.X_ACCESS_TOKEN,
        config.X_ACCESS_TOKEN_SECRET,
    )
    api = tweepy.API(auth)
    return client, api


def verify_credentials() -> str:
    """接続テスト。成功すれば @ユーザー名 を返す。"""
    client, _ = _clients()
    me = client.get_me()
    username = me.data.username if me and me.data else "?"
    _log().info("X 接続OK: @%s", username)
    return username


def post(text: str, image_path: str | None = None) -> dict:
    """投稿を実行し、{'tweet_id', 'tweet_url'} を返す。"""
    client, api = _clients()

    media_ids = None
    if image_path:
        try:
            media = api.media_upload(filename=str(image_path))
            media_ids = [media.media_id]
            _log().info("画像をアップロードしました: %s", image_path)
        except Exception as e:  # noqa: BLE001
            log_error(f"画像アップロードに失敗。テキストのみで投稿します: {e}")
            media_ids = None

    resp = client.create_tweet(text=text, media_ids=media_ids)
    tweet_id = resp.data["id"]
    username = ""
    try:
        me = client.get_me()
        username = me.data.username if me and me.data else ""
    except Exception:  # noqa: BLE001
        pass
    url = f"https://x.com/{username}/status/{tweet_id}" if username else (
        f"https://x.com/i/status/{tweet_id}"
    )
    _log().info("投稿しました: %s", url)
    return {"tweet_id": str(tweet_id), "tweet_url": url}
