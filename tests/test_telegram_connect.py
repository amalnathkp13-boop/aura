"""telegram-connect: turn a BotFather token into a configured alert channel by
resolving the chat id from the latest message the user sent the bot."""
import pytest
from aura.guardian.notify import telegram_connect


def _updates(*chats):
    return {"ok": True, "result": [
        {"update_id": i, "message": {"message_id": i, "chat": c, "text": "/start"}}
        for i, c in enumerate(chats)]}


def test_connect_resolves_latest_chat():
    fetched = []
    def fetch(url):
        fetched.append(url)
        return _updates({"id": 111, "first_name": "Old"},
                        {"id": 42424242, "first_name": "Amal"})
    chat_id, name = telegram_connect("TOK123", fetch=fetch)
    assert chat_id == "42424242"
    assert name == "Amal"
    assert "botTOK123/getUpdates" in fetched[0]


def test_connect_group_chat_uses_title():
    def fetch(url):
        return _updates({"id": -100777, "title": "Family Home", "type": "group"})
    chat_id, name = telegram_connect("T", fetch=fetch)
    assert chat_id == "-100777"
    assert name == "Family Home"


def test_connect_without_messages_explains_what_to_do():
    with pytest.raises(RuntimeError, match="send your bot"):
        telegram_connect("T", fetch=lambda url: {"ok": True, "result": []})


def test_connect_skips_non_message_updates():
    def fetch(url):
        return {"ok": True, "result": [
            {"update_id": 1, "my_chat_member": {}},
            {"update_id": 2, "message": {"chat": {"id": 7, "first_name": "A"}}}]}
    assert telegram_connect("T", fetch=fetch)[0] == "7"
