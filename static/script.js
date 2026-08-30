/*
 * ichibom Minecraft Server 配信者一覧 - フロントエンドの動き

 * 1. ページを開いたら /api/streams を1回呼んでカードを表示する
 * 2. 30秒ごとに同じAPIを呼び直して、カードを最新の状態に書き換える
 * 3. 表示は「配信中の人を先頭に」並べ替える
 *
 * セキュリティ上の注意:
 *   配信タイトルや表示名はTwitch側(=配信者本人)が自由に設定できる文字列なので、
 *   innerHTML でそのまま差し込むとHTMLタグを混入されてしまう危険がある(XSS)。
 *   そのため、このファイルでは必ず textContent を使ってテキストとして挿入する。
 */

const REFRESH_INTERVAL_MS = 30000;

const grid = document.getElementById("streamer-grid");
const statusNote = document.getElementById("status-note");

function createAvatar(streamer) {
  const wrap = document.createElement("div");
  wrap.className = "avatar-wrap";

  if (streamer.avatar_url) {
    const img = document.createElement("img");
    img.className = "avatar";
    img.src = streamer.avatar_url;
    img.alt = streamer.display_name;
    img.loading = "lazy";
    wrap.appendChild(img);
  } else {
    const placeholder = document.createElement("div");
    placeholder.className = "avatar avatar-placeholder";
    placeholder.textContent = streamer.display_name.charAt(0);
    wrap.appendChild(placeholder);
  }

  return wrap;
}

function createCard(streamer) {
  const isLive = streamer.is_live;

  // 配信中はクリックできる<a>タグ、オフラインはただの<div>にする。
  // こうすることで「どれがクリックできるのか」が構造レベルでもはっきりする。
  const card = document.createElement(isLive ? "a" : "div");
  card.className = `card ${isLive ? "live" : "offline"}`;
  if (isLive) {
    card.href = streamer.url;
    card.target = "_blank";
    card.rel = "noopener noreferrer";
  }

  const badge = document.createElement("div");
  badge.className = "badge";
  badge.textContent = isLive ? "🔴 LIVE" : "OFFLINE";
  card.appendChild(badge);

  card.appendChild(createAvatar(streamer));

  const name = document.createElement("div");
  name.className = "name";
  name.textContent = streamer.display_name;
  card.appendChild(name);

  if (isLive) {
    const game = document.createElement("div");
    game.className = "game";
    game.textContent = streamer.game_name || "配信中";
    card.appendChild(game);

    const viewers = document.createElement("div");
    viewers.className = "viewers";
    viewers.textContent = `👥 ${streamer.viewer_count ?? 0} viewers`;
    card.appendChild(viewers);

    if (streamer.title) {
      const title = document.createElement("div");
      title.className = "title";
      title.textContent = streamer.title;
      card.appendChild(title);
    }
  }

  return card;
}

function sortLiveFirst(streamers) {
  return [...streamers].sort((a, b) => Number(b.is_live) - Number(a.is_live));
}

function renderStreamers(streamers) {
  grid.innerHTML = "";

  if (streamers.length === 0) {
    const empty = document.createElement("p");
    empty.className = "loading";
    empty.textContent = "配信者が登録されていません。";
    grid.appendChild(empty);
    return;
  }

  sortLiveFirst(streamers).forEach((streamer) => {
    grid.appendChild(createCard(streamer));
  });
}

async function loadStreams() {
  try {
    const res = await fetch("/api/streams");
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();

    renderStreamers(data.streamers || []);

    statusNote.textContent = data.error
      ? "⚠️ 最新の情報を取得できませんでした(前回取得できた情報を表示しています)"
      : "";
  } catch (err) {
    console.error("配信状況の取得に失敗しました:", err);
    statusNote.textContent = "⚠️ 配信状況を取得できませんでした。しばらくしてから再読み込みしてください。";
  }
}

loadStreams();
setInterval(loadStreams, REFRESH_INTERVAL_MS);
