# ichibom Minecraft Server 配信者一覧ポータル (MVP)

ichibom Minecraft Server のメンバーが、今誰がTwitchで配信中かをひと目で確認できる
Webページです。Python初心者の方でも、1ステップずつ動作確認しながら
構築できるように手順を分けています。

## 全体の仕組み(なぜこの構成なのか)

```
[Twitch] --Helix API--> [twitch_api.py] --> [app.py(Flask)] --キャッシュ--> [/api/streams(JSON)]
                                                                                    ^
                                                                                    |
                                                                    30秒ごとにfetch (script.js)
                                                                                    |
                                                                                    v
                                                                        [index.html] 画面を書き換え
```

- **Client Secretはサーバー(Python)だけが知っていて、ブラウザには絶対に渡さない**
  ブラウザに渡すのは「もう加工済みのJSON(誰が配信中か、視聴者数など)」だけです。
  こうすることで、ページのHTML/JSを見られてもTwitchの機密情報は漏れません。
- **Flaskがキャッシュを持つことで、Twitch APIへの問い合わせを1箇所に集約する**
  60人がページを開いても、Twitchへの問い合わせは「サーバーが30秒に1回」で済みます。
  もしブラウザから直接Twitch APIを叩く設計にしてしまうと、開いている人数分だけ
  リクエストが増えてしまい、レート制限にすぐ引っかかります。
- **ブラウザ側は30秒ごとに `/api/streams` を再取得するだけ**
  ページの再読み込み(F5)は不要で、カード部分だけが自動的に書き換わります。

---

## STEP 1. Python環境を準備する

**何をするか:** Python 3.10以降がインストールされているか確認し、この
プロジェクト専用の仮想環境(venv)を作ります。

**なぜ必要か:** 仮想環境を使わずに `pip install` すると、他のプロジェクトの
ライブラリと衝突することがあります。プロジェクトごとに専用の環境を
用意するのがPythonの基本作法です。

**操作するファイル:** なし(ターミナル操作のみ)

```bash
cd ichibom_stream_portal
python --version        # 3.10以上であればOK
python -m venv venv

# 仮想環境を有効化
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate
```

**確認方法:** ターミナルの先頭に `(venv)` と表示されればOKです。

**エラーが出たら:** `python` コマンドが見つからない場合、`python3` で
試してください。Windowsで実行ポリシーのエラーが出る場合は
`PowerShell` ではなく `コマンドプロンプト` を使うと簡単です。

---

## STEP 2. 必要なライブラリをインストールする

**何をするか:** Flask・requests・python-dotenv をインストールします。

**なぜ必要か:**
- `Flask` … Webページを表示するためのフレームワーク
- `requests` … Twitch APIにHTTPリクエストを送るためのライブラリ
- `python-dotenv` … `.env` ファイルから設定を読み込むためのライブラリ

**操作するファイル:** `requirements.txt`(すでに用意済みです)

```bash
pip install -r requirements.txt
```

**確認方法:** `pip list` でFlask, requests, python-dotenvが表示されればOK。

**エラーが出たら:** venvが有効化されているか(`(venv)` が表示されているか)を
確認してください。

---

## STEP 3. Twitch Developer Console でアプリを作成する

**何をするか:**
1. https://dev.twitch.tv/console にTwitchアカウントでログイン
2. 「Register Your Application」からアプリを新規登録
   - Name: 好きな名前(例: `ichibom-stream-portal`)
   - OAuth Redirect URLs: `http://localhost:5000`(MVPでは実際には使いませんが必須項目です)
   - Category: `Website Integration` など
3. 作成後、そのアプリの画面で **Client ID** を確認
4. 「New Secret」ボタンを押して **Client Secret** を発行(表示は1度きりなので必ずコピー)

**なぜ必要か:** Twitch APIを呼ぶには、公式に登録したアプリ専用の
Client ID / Client Secretが必要です。個人情報ではなく「アプリの身分証」です。

**操作するファイル:** なし(Twitchの管理画面での作業)

**確認方法:** Client IDとClient Secretの文字列が手元にあればOK。

**エラーが出たら:** Client Secretを再発行すると前のSecretは無効になります。
控え忘れた場合は再発行してください。

---

## STEP 4. Client ID / Secretを `.env` に設定する

**何をするか:** `.env.example` をコピーして `.env` を作り、STEP3で取得した
値を書き込みます。

**なぜ必要か:** Client Secretのような機密情報を `app.py` や `index.html` に
直接書いてしまうと、Gitにコミットした時点で世界中に公開されてしまいます。
`.env` は `.gitignore` に登録済みなので、Gitには含まれません。

**操作するファイル:** `.env`(新規作成)

```bash
cp .env.example .env
```

`.env` を開いて、次のように書き換えます。

```
TWITCH_CLIENT_ID=（STEP3で取得したClient ID）
TWITCH_CLIENT_SECRET=（STEP3で取得したClient Secret）
CACHE_TTL_SECONDS=30
```

**確認方法:** `.env` ファイルが `ichibom_stream_portal/` 直下にあり、
値が正しく貼り付けられていればOK。

**エラーが出たら:** `git status` を実行して `.env` が「Untracked」や
「Changes」に出てこないこと(＝Gitに無視されていること)を確認してください。

---

## STEP 5. PythonからTwitch APIに接続してみる (動作確認)

**何をするか:** Pythonの対話モードで、`twitch_api.py` が正しくトークンを
取得できるか確認します。

**なぜ必要か:** いきなりFlaskを動かすと、エラーの原因がFlask側なのか
Twitch API側なのか切り分けづらくなります。先に「素のPython」で
API接続だけを確認しておくと、問題の切り分けが簡単になります。

**操作するファイル:** なし(対話確認のみ)

```bash
python
```

```python
>>> from dotenv import load_dotenv
>>> import os
>>> load_dotenv()
>>> from twitch_api import TwitchClient
>>> client = TwitchClient(os.environ["TWITCH_CLIENT_ID"], os.environ["TWITCH_CLIENT_SECRET"])
>>> client.get_users(["twitchdev"])
```

**確認方法:** `{'twitchdev': {...ユーザー情報...}}` のような辞書が
返ってくればOKです。

**エラーが出たら:**
- `401 Unauthorized` → Client ID/Secretのコピーミスを疑ってください。
- `ValueError` → `.env` が読み込めていません。`load_dotenv()` を
  忘れていないか、`.env` の場所が合っているか確認してください。

---

## STEP 6. 配信中かどうかを取得してみる

**何をするか:** STEP5に続けて、`get_streams` も試します。

```python
>>> client.get_streams(["twitchdev"])
```

**なぜ必要か:** `get_users` と `get_streams` は返ってくる内容が違います。
- `get_users` → 配信していなくても常に情報が返る(アイコン画像など)
- `get_streams` → **配信中の人だけ** が結果に含まれる(オフラインの人は
  結果に登場しない)

この違いを理解しておくと、`app.py` の「配信中/オフラインの判定ロジック」
(`stream is not None` で判定している部分)が読みやすくなります。

**確認方法:** `twitchdev` が配信中であれば辞書が、オフラインなら
空の辞書 `{}` が返ります。

---

## STEP 7. FlaskでWebページを表示する

**何をするか:** `app.py` を起動し、ブラウザで `http://localhost:5000` を開きます。

**なぜ必要か:** ここまでの部品(streamers.py / twitch_api.py)を
Flaskにつなぎ込み、実際にブラウザから見える状態にします。

**操作するファイル:** `app.py`, `templates/index.html`(すでに用意済み)

```bash
python app.py
```

**確認方法:** ターミナルに `Running on http://127.0.0.1:5000` と表示され、
ブラウザでページタイトルと「NOW STREAMING」の見出しが表示されればOKです。
(この時点ではまだカードは「読み込み中...」のままでも問題ありません)

**エラーが出たら:**
- `ValueError: TWITCH_CLIENT_ID...` → `.env` の設定を再確認してください。
- ポートが使用中というエラー → 他のFlaskアプリが起動していないか確認するか、
  `app.run(debug=True, port=5001)` のようにポート番号を変えてください。

---

## STEP 8. 配信者を登録してアイコンを表示する

**何をするか:** `streamers.py` を開き、実際にichibom鯖で配信している人の
**Twitchログイン名**(表示名ではなく、URLに使われる英数字の名前)を登録します。

**なぜ必要か:** `streamers.py` がこのアプリの「配信者名簿」です。
ここに追加した人だけがページに表示されます。

**操作するファイル:** `streamers.py`

```python
STREAMERS = [
    {"display_name": "いちぞー", "twitch_login": "実際のログイン名"},
    {"display_name": "やんゆい", "twitch_login": "実際のログイン名"},
    # 60人に増やす場合は、この形式でどんどん追加していくだけでOK
]
```

**確認方法:** Flaskを再起動(`Ctrl+C` → `python app.py`)し、ブラウザを
再読み込みすると、登録した人数分のカードが表示され、Twitchのアイコン画像が
表示されます。

**エラーが出たら:** アイコンが表示されない場合、ログイン名の入力ミスが
一番多い原因です。該当のTwitchページを開き、URLの末尾と見比べてください。

---

## STEP 9. LIVE状態のCSSアニメーションを確認する

**何をするか:** 登録した配信者のうち誰か1人に実際に配信を開始してもらう
(または `twitchdev` のような、配信していることの多いテストアカウントを
一時的に登録する)ことで、LIVE表示を確認します。

**なぜ必要か:** オフライン状態のCSS(グレースケール)と、配信中のCSS
(赤い光のアニメーション、LIVEバッジの点滅)がそれぞれ意図通りに
切り替わるかを目視で確認します。

**操作するファイル:** `static/style.css` (見た目を調整したい場合はここを編集)

**確認方法:**
- 配信中のカード → アイコン周りが赤くふわっと光り、「🔴 LIVE」が点滅し、
  ゲーム名と視聴者数が表示される
- オフラインのカード → アイコンが薄暗いグレースケールになり、
  「OFFLINE」とだけ表示される

**エラーが出たら:** アニメーションが動かない場合、ブラウザのキャッシュが
古いCSSを読み込んでいる可能性があります。スーパーリロード
(Windows: `Ctrl+Shift+R` / Mac: `Cmd+Shift+R`)を試してください。

---

## STEP 10. 自動更新を確認する

**何をするか:** ページを開いたまま何もせずに30秒以上待ち、配信状態の
変化(配信開始/終了、視聴者数の増減)が自動でカードに反映されるか確認します。

**なぜ必要か:** `static/script.js` が30秒ごとに `/api/streams` を
呼び出す仕組みになっています。ブラウザの開発者ツール(F12) →
「Network」タブを開いておくと、30秒ごとに `streams` へのリクエストが
発生している様子を確認できます。

**操作するファイル:** `static/script.js`
(更新間隔を変えたい場合は `REFRESH_INTERVAL_MS` の値を変更してください)

**確認方法:** ページをリロードしなくても、視聴者数などの表示が
数字だけ変わっていけばOKです。

**エラーが出たら:** 何も更新されない場合、ブラウザの開発者ツールの
「Console」タブにエラーが出ていないか確認してください。
`fetch` が失敗している場合は、Flaskサーバーがまだ起動しているか
確認してください。

---

## ここまでできたらMVP完成です

- Flaskでページを表示 ✅
- Twitch APIから配信状況を取得 ✅
- カード形式で表示 ✅
- 配信中はアイコンが光る ✅
- LIVE / ゲーム名 / 視聴者数を表示 ✅
- オフラインは区別して表示 ✅
- カードをクリックしてTwitchへ移動 ✅
- 30秒ごとに自動更新 ✅

---

## レート制限・負荷についての設計メモ

- Twitch APIは「1回のリクエストで最大100件のログイン名」をまとめて
  問い合わせできます。ichibom鯖の60人規模なら、`get_users` / `get_streams`
  それぞれ**1回のリクエスト**で済みます(`twitch_api.py` の `CHUNK_SIZE`)。
- サーバー側で30秒キャッシュしているため、100人が同時にページを開いても
  Twitchへのリクエスト数は増えません(閲覧者数と無関係に一定)。
- アイコン画像などほぼ変化しない情報(`get_users`)は1時間キャッシュ、
  配信状況(`get_streams`)は30秒キャッシュ、と更新頻度を分けることで
  無駄なAPI呼び出しを減らしています。
- Twitch API呼び出しが失敗した場合(ネットワークエラーや一時的な障害)は、
  直前まで取得できていた情報を表示し続け、ページが真っ白になったり
  クラッシュしたりしないようにしています。

## 今後の拡張(このMVPの上に足していく想定)

- YouTube配信への対応(`youtube_api.py` を追加し、`streamers.py` に
  `platform` フィールドを持たせる)
- 配信者検索・Minecraft配信だけ表示するフィルター(フロントエンドの
  `script.js` に検索/フィルターUIを追加)
- 配信開始からの経過時間(`get_streams` が返す `started_at` を利用)
- サーバー内のプレイヤー一覧、お知らせ、イベント情報などのポータル機能

## 本番運用に向けて(参考)

- `app.run(debug=True)` は開発用です。実際に公開する場合は
  `gunicorn` などのWSGIサーバー経由で動かしてください。
- `.env` の中身は絶対に公開リポジトリにコミットしないでください。
