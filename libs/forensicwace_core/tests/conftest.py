import sqlite3
from pathlib import Path

import pytest

# Minimal synthetic msgstore.db: schema subset + fake rows. Never real data.
ANDROID_FIXTURE_SQL = """
CREATE TABLE jid (_id INTEGER PRIMARY KEY, user TEXT, server TEXT, raw_string TEXT);
CREATE TABLE chat_view (_id INTEGER PRIMARY KEY, jid_row_id INTEGER, subject TEXT,
                        raw_string_jid TEXT, last_message_row_id INTEGER);
CREATE TABLE message (_id INTEGER PRIMARY KEY, chat_row_id INTEGER, from_me INTEGER,
                      timestamp INTEGER, message_type INTEGER, text_data TEXT);
CREATE TABLE message_media (message_row_id INTEGER, file_path TEXT, file_size INTEGER,
                            media_caption TEXT, mime_type TEXT);
CREATE TABLE message_location (message_row_id INTEGER, chat_row_id INTEGER,
                               latitude REAL, longitude REAL);

INSERT INTO jid VALUES (1, '390000000001', 's.whatsapp.net', '390000000001@s.whatsapp.net');
INSERT INTO jid VALUES (2, 'group1', 'g.us', 'group1@g.us');
INSERT INTO chat_view VALUES (1, 1, NULL, '390000000001@s.whatsapp.net', 2);
INSERT INTO chat_view VALUES (2, 2, 'Test Group', 'group1@g.us', 3);
INSERT INTO message VALUES (1, 1, 0, 1700000000000, 0, 'hello from contact');
INSERT INTO message VALUES (2, 1, 1, 1700000100000, 0, 'hello back');
INSERT INTO message VALUES (3, 2, 0, 1700000200000, 0, 'group message');
"""


@pytest.fixture
def android_backup_root(tmp_path: Path) -> Path:
    backup_dir = tmp_path / "extraction_test"
    backup_dir.mkdir()
    db_path = backup_dir / "msgstore.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(ANDROID_FIXTURE_SQL)
    conn.commit()
    conn.close()
    return tmp_path
