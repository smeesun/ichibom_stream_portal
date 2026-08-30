"""
Twitch Helix API とやり取りするためのモジュール。

このファイルの役割は3つだけです。

  1. App Access Token を取得する (Client Credentials Flow)
     -> Twitch APIを呼ぶために必要な「通行証」を取ってくる処理
  2. Get Users で、配信者の基本情報(アイコン画像URLなど)を取得する
     -> あまり変化しない情報
  3. Get Streams で、今まさに配信中かどうか・ゲーム・視聴者数を取得する
     -> 数十秒単位で変化する情報

Client ID / Client Secret などの機密情報は、このファイルには一切書きません。
呼び出し側 (app.py) が .env から読み込んだ値を渡してくる形にしています。
"""

import time
import threading
import logging

import requests

logger = logging.getLogger(__name__)

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
USERS_URL = "https://api.twitch.tv/helix/users"
STREAMS_URL = "https://api.twitch.tv/helix/streams"

# Twitch APIは、1回のリクエストで最大100件までしかID/ログイン名を指定できない。
# 60人程度なら1回のリクエストで済むが、将来もっと増えても壊れないように
# あらかじめ100件ずつに分割して呼び出すようにしておく。
CHUNK_SIZE = 100
REQUEST_TIMEOUT_SECONDS = 10


class TwitchClient:
    """Twitch Helix APIへの問い合わせをまとめて担当するクラス"""

    def __init__(self, client_id, client_secret):
        if not client_id or not client_secret:
            raise ValueError(
                "TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET が設定されていません。"
                ".env ファイルを確認してください。"
            )
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token = None
        self._token_expires_at = 0.0
        self._lock = threading.Lock()

    def _fetch_new_token(self):
        """Client Credentials Flow で新しいApp Access Tokenを取得する"""
        response = requests.post(
            TOKEN_URL,
            params={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        self._access_token = data["access_token"]
        # 期限ぎりぎりで失効して失敗するのを避けるため、60秒早めに切れた扱いにする
        self._token_expires_at = time.time() + data.get("expires_in", 0) - 60
        logger.info("Twitch App Access Token を取得しました。")

    def _get_valid_token(self):
        with self._lock:
            if not self._access_token or time.time() >= self._token_expires_at:
                self._fetch_new_token()
            return self._access_token

    def _headers(self):
        return {
            "Client-Id": self.client_id,
            "Authorization": f"Bearer {self._get_valid_token()}",
        }

    def _get_paginated(self, url, param_key, values):
        """
        同じキーを繰り返すクエリパラメータ (?login=a&login=b...) を
        100件ずつに分割して呼び出す共通処理。
        """
        results = []
        for i in range(0, len(values), CHUNK_SIZE):
            chunk = values[i : i + CHUNK_SIZE]
            if not chunk:
                continue
            results.extend(self._request_chunk(url, param_key, chunk))
        return results

    def _request_chunk(self, url, param_key, chunk):
        response = requests.get(
            url,
            headers=self._headers(),
            params={param_key: chunk},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code == 401:
            # トークンが失効していた場合、1回だけ取り直して再試行する
            with self._lock:
                self._fetch_new_token()
            response = requests.get(
                url,
                headers=self._headers(),
                params={param_key: chunk},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        response.raise_for_status()
        return response.json().get("data", [])

    def get_users(self, logins):
        """
        Get Users: ユーザーID・表示名・アイコン画像URLなど、
        あまり変化しない基本情報をまとめて取得する。

        戻り値: {ログイン名(小文字): ユーザー情報の辞書, ...}
        """
        if not logins:
            return {}
        data = self._get_paginated(USERS_URL, "login", logins)
        return {user["login"].lower(): user for user in data}

    def get_streams(self, logins):
        """
        Get Streams: 現在「配信中」のユーザーの情報だけが返ってくる。
        オフラインのユーザーは結果に含まれない点に注意。

        戻り値: {ログイン名(小文字): 配信情報の辞書, ...}
        """
        if not logins:
            return {}
        data = self._get_paginated(STREAMS_URL, "user_login", logins)
        return {stream["user_login"].lower(): stream for stream in data}
