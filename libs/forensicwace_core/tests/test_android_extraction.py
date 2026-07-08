from forensicwace_core.backups import android as backups
from forensicwace_core.whatsapp import android


def test_list_backups(android_backup_root):
    found = backups.list_backups(android_backup_root)
    assert len(found) == 1
    assert found[0].folder == "extraction_test"
    assert found[0].db_file == "msgstore.db"


def test_chat_list(android_backup_root):
    db = backups.resolve_db_path(android_backup_root, "extraction_test")
    chats = android.get_chat_list(db)
    assert len(chats) == 1
    assert chats[0]["PhoneNumber"] == "390000000001"
    assert chats[0]["NumberOfMessages"] == 2


def test_private_chat_is_parameterized(android_backup_root):
    db = backups.resolve_db_path(android_backup_root, "extraction_test")
    counters, messages = android.get_private_chat(db, "390000000001")
    assert counters["TotalMessages"] == 2
    assert [m["text_data"] for m in messages] == ["hello from contact", "hello back"]

    # A hostile "phone number" must be treated as data, not SQL
    counters, messages = android.get_private_chat(db, "x' OR '1'='1")
    assert messages == []


def test_group_list(android_backup_root):
    db = backups.resolve_db_path(android_backup_root, "extraction_test")
    groups = android.get_group_list(db)
    assert [g["Group_Name"] for g in groups] == ["Test Group"]


def test_filtered_messages_for_analysis(android_backup_root):
    db = backups.resolve_db_path(android_backup_root, "extraction_test")
    rows = android.get_filtered_messages(db, contacts=["390000000001"], groups=["Test Group"])
    assert {r["text"] for r in rows} == {"hello from contact", "hello back", "group message"}

    only_received = android.get_filtered_messages(
        db, contacts=["390000000001"], include_sent=False, include_received=True
    )
    assert [r["text"] for r in only_received] == ["hello from contact"]
