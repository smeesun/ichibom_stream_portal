"""
ichibom鯖 配信者リスト設定ファイル

ここに配信者を追加していくだけで、Webページに表示する配信者を増やせます。
将来的に60人くらいまで増やす想定なので、リストに辞書を追加するだけで
反映されるようにしてあります。

【重要】twitch_login について
--------------------------------
Twitchには「表示名 (display_name)」と「ログイン名 (login)」の2種類の
名前があります。

  例: 表示名が「イチゾー」でも、ログイン名(URLに使われる部分)は
      "ichizo_game" のように英数字＆小文字のみ、ということがあります。

  https://www.twitch.tv/ichizo_game
                         ^^^^^^^^^^^ ← これが twitch_login

表示名は日本語や大文字を含むことがありますが、Twitch APIへの問い合わせ
(Get Users / Get Streams) や配信URLの組み立てには、必ずこの
「ログイン名」を使う必要があります。表示名はTwitch側から取得して
使う(twitch_api.py の get_users の結果を使う)ので、ここには書きません。

配信者を追加するときは、対象の配信者のTwitchページを開いて
アドレスバーのURLの最後の部分(ログイン名)をコピーしてきてください。
"""

STREAMERS = [
    {
        "display_name": "いちぞー",
        "twitch_login": "ichizo_login",  # 実際のログイン名に書き換えてください
    },
    {
        "display_name": "やんゆい",
        "twitch_login": "yanyui_login",  # 実際のログイン名に書き換えてください
    },
    {
        # Twitchが公式に用意しているテスト用アカウント。
        # 動作確認用に、実在するアカウントとしてそのまま使えます。
        "display_name": "テストユーザー",
        "twitch_login": "twitchdev",
    },
]


def get_twitch_logins():
    """登録されている全員のログイン名の一覧を返す"""
    return [streamer["twitch_login"] for streamer in STREAMERS]
