SELECT _id, chat_row_id, from_me,
       datetime(timestamp / 1000, 'unixepoch', 'localtime') AS readable_timestamp,
       message_type,
       text_data
FROM message
WHERE chat_row_id = (
    SELECT chat_view._id
    FROM jid
    INNER JOIN chat_view ON jid._id = chat_view.jid_row_id
    WHERE jid.user LIKE :phone_pattern
)
