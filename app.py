"""
ichibom Minecraft Server 配信者一覧ページ (MVP)

このファイルの役割:
  - Flaskで「/」(トップページ) と「/api/streams」(配信状況API) を用意する
  - streamers.py の設定 + Twitch APIの結果を組み合わせてJSONを作る
  - Twitch APIへの問い合わせ回数を抑えるため、結果を一定時間キャッシュする
    (何人が同時にページを開いても、Twitchへの問い合わせは増えない)

ブラウザ側 (static/script.js) は、この /api/streams を30秒おきに呼び出して
画面を書き換えることで、リロードなしの自動更新を実現している。
"""

import os
import time
import logging
import threading

import requests
from flask import Flask, jsonify, render_template
from dotenv import load_dotenv

from streamers import STREAMERS, get_twitch_logins
from twitch_api import TwitchClient

# .env ファイルに書いた環境変数を読み込む (TWITCH_CLIENT_ID など)
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

CLIENT_ID = os.environ.get("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.environ.get("TWITCH_CLIENT_SECRET")

# Twitch APIへ実際に問い合わせて良い最短間隔(秒)。
# ここを短くしすぎるとTwitchのレート制限に引っかかる可能性があるため、
# 30秒程度を推奨(フロントエンドの自動更新間隔と合わせてある)。
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "30"))

# アイコン画像URLなど、ほぼ変化しない情報は長めにキャッシュする
USER_INFO_TTL_SECONDS = 60 * 60  # 1時間

twitch_client = TwitchClient(CLIENT_ID, CLIENT_SECRET)

_status_cache_lock = threading.Lock()
_status_cache = {"data": [], "fetched_at": 0.0, "error": False}

_user_info_cache_lock = threading.Lock()
_user_info_cache = {"data": {}, "fetched_at": 0.0}


def _get_user_info():
    """Get Users の結果を1時間キャッシュして使い回す"""
    with _user_info_cache_lock:
        is_fresh = time.time() - _user_info_cache["fetched_at"] < USER_INFO_TTL_SECONDS
        if is_fresh and _user_info_cache["data"]:
            return _user_info_cache["data"]
        try:
            data = twitch_client.get_users(get_twitch_logins())
            _user_info_cache["data"] = data
            _user_info_cache["fetched_at"] = time.time()
        except requests.exceptions.RequestException:
            logger.exception("Get Users の取得に失敗しました。前回のキャッシュを使用します。")
        return _user_info_cache["data"]


def _build_streamer_status():
    """streamers.py の設定 + Twitch APIの結果をマージして一覧を作る"""
    users = _get_user_info()

    fetch_error = False
    try:
        streams = twitch_client.get_streams(get_twitch_logins())
    except requests.exceptions.RequestException:
        logger.exception("Get Streams の取得に失敗しました。")
        streams = {}
        fetch_error = True

    result = []
    for streamer in STREAMERS:
        login = streamer["twitch_login"].lower()
        user = users.get(login)
        stream = streams.get(login)

        result.append(
            {
                "display_name": streamer["display_name"],
                "twitch_login": streamer["twitch_login"],
                "url": f"https://www.twitch.tv/{streamer['twitch_login']}",
                "avatar_url": user.get("profile_image_url") if user else None,
                "is_live": stream is not None,
                "game_name": (stream or {}).get("game_name"),
                "viewer_count": (stream or {}).get("viewer_count"),
                "title": (stream or {}).get("title"),
            }
        )

    return result, fetch_error


@app.route("/")
def index():
    return render_template("index.html", server_name="ichibom Minecraft Server")


@app.route("/api/streams")
def api_streams():
    """
    配信状況をJSONで返すAPI。
    キャッシュが新しければTwitchへは問い合わせず、キャッシュをそのまま返す。
    """
    with _status_cache_lock:
        is_stale = time.time() - _status_cache["fetched_at"] >= CACHE_TTL_SECONDS
        if is_stale:
            streamers, fetch_error = _build_streamer_status()
            # 取得に成功した場合、またはまだ一度もキャッシュがない場合だけ内容を更新する。
            # 失敗時は「古いけど直前まで正しかった情報」を表示し続ける。
            if not fetch_error or not _status_cache["data"]:
                _status_cache["data"] = streamers
            _status_cache["fetched_at"] = time.time()
            _status_cache["error"] = fetch_error

        return jsonify(
            {
                "streamers": _status_cache["data"],
                "updated_at": _status_cache["fetched_at"],
                "error": _status_cache["error"],
            }
        )


if __name__ == "__main__":
    # デバッグ用サーバー。本番運用する場合は gunicorn などを使ってください。
    app.run(debug=True, port=5000)
