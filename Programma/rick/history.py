from datetime import datetime, timezone

from . import config, jsonstore

NO_GAME_KEY_IT = "Senza titolo"
NO_GAME_KEY_EN = "Untitled"


def is_untitled(game: str) -> bool:
    """The catch-all bucket for chats with no game name - it can mix many
    different games, so it's never treated as one game's memory."""
    return game.strip() in ("", NO_GAME_KEY_IT, NO_GAME_KEY_EN)


def _load() -> dict:
    data = jsonstore.read_json(config.HISTORY_FILE, {})
    return data if isinstance(data, dict) else {}


def _save(data: dict) -> None:
    jsonstore.write_json(config.HISTORY_FILE, data)


def _timestamp_of(entry: dict) -> str:
    # ISO-8601 UTC strings sort chronologically as text - including older
    # whole-second ones next to newer microsecond ones ("...:00+00:00" sorts
    # before "...:00.5+00:00", since "+" < ".")
    return entry.get("timestamp", "")


def add_entry(game: str, question: str, answer: str) -> None:
    """Appends one question/answer pair to the given game's binder, creating
    it if it doesn't exist yet."""
    game = game.strip() or NO_GAME_KEY_IT
    data = _load()
    data.setdefault(game, []).append(
        {
            "question": question,
            "answer": answer,
            # microseconds, not seconds: two entries in the same second
            # (e.g. merging binders) must still sort in the right order
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        }
    )
    _save(data)


def list_games() -> list[str]:
    """Game titles with saved history, most recently active first."""
    data = _load()

    def last_timestamp(game: str) -> str:
        entries = data[game]
        return _timestamp_of(entries[-1]) if entries else ""

    return sorted(data.keys(), key=last_timestamp, reverse=True)


def get_game_history(game: str) -> list[dict]:
    """Saved question/answer entries for one game, oldest first."""
    return _load().get(game, [])


def rename_game(old_name: str, new_name: str) -> None:
    """Moves old_name's saved entries under new_name, merging into
    new_name's entries (kept in chronological order) if it already has
    some. A no-op if old_name has no saved entries yet (nothing to move),
    if the name didn't actually change, or if new_name is blank - callers
    resolve a blank name to the right language's untitled bucket first."""
    old_name, new_name = old_name.strip(), new_name.strip()
    if not old_name or not new_name or old_name == new_name:
        return
    data = _load()
    if old_name not in data:
        return
    merged = data.get(new_name, []) + data.pop(old_name)
    merged.sort(key=_timestamp_of)
    data[new_name] = merged
    _save(data)


def delete_game(game: str) -> None:
    """Permanently removes a binder and all its saved entries."""
    data = _load()
    if game in data:
        del data[game]
        _save(data)
