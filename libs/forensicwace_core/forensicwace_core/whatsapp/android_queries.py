"""Dynamically assembled Android queries (analysis message selection).

The static extraction queries live in the schema registry
(``schemas/whatsapp/android/...``). These helpers are templates whose IN
clauses are sized per request; the placeholders are always bound parameters.
"""

CHATS_BY_CONTACTS = """
SELECT chat_view._id, jid.raw_string, jid.user
FROM jid
INNER JOIN chat_view ON jid._id = chat_view.jid_row_id
WHERE jid.user IN ({placeholders})
"""

CHATS_BY_GROUP_SUBJECTS = """
SELECT _id, jid_row_id, subject
FROM chat_view
WHERE subject IN ({placeholders})
"""

MESSAGE_MEDIA = """
SELECT message_row_id, file_path, file_size, media_caption, mime_type
FROM message_media
WHERE message_row_id = :message_id
"""
