"""Parameterized SQL for Android ``msgstore.db`` (modern chat_view schema)."""

CHAT_LIST = """
SELECT SUBSTRING(PhoneNumber, 1, 12) AS PhoneNumber,
       datetime(MessageDate / 1000, 'unixepoch', 'localtime') as MessageDate,
       NumberOfMessages
FROM (
    SELECT jid.user AS PhoneNumber,
           chat_view.subject,
           chat_view.last_message_row_id,
           message.chat_row_id,
           message.timestamp as MessageDate
    FROM chat_view
    JOIN message ON chat_view.last_message_row_id = message._id
    LEFT JOIN jid ON chat_view.jid_row_id = jid._id
    WHERE jid.server = 's.whatsapp.net'
) AS contact
JOIN (
    SELECT chat_row_id, COUNT(message._id) AS NumberOfMessages
    FROM message
    GROUP BY chat_row_id
) AS chat_count ON contact.chat_row_id = chat_count.chat_row_id
"""

PRIVATE_CHAT_COUNTERS = """
SELECT count(case when True then 1 else null end) as TotalMessages,
       count(case when message_type = 15 then 1 else null end) as DeletedMessages,
       count(case when message_type IN ('1','42','2','43','3','13','5','7','9') then 1 else null end) as Attachments,
       count(case when message_type IN (1, 42) then 1 else null end) as Images,
       count(case when message_type = 2 then 1 else null end) as Audio,
       count(case when message_type IN (3, 43) then 1 else null end) as Videos,
       count(case when message_type = 13 then 1 else null end) as GIF,
       count(case when message_type = 5 then 1 else null end) as Positions,
       count(case when message_type = 7 then 1 else null end) as Url,
       count(case when message_type = 9 then 1 else null end) as File,
       count(case when message_type = 4 then 1 else null end) as Contacts,
       count(case when message_type = 20 then 1 else null end) as Stickers
FROM message
WHERE chat_row_id = (
    SELECT chat_view._id
    FROM jid
    INNER JOIN chat_view ON jid._id = chat_view.jid_row_id
    WHERE jid.user LIKE :phone_pattern
)
"""

PRIVATE_CHAT_MESSAGES = """
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
"""

GROUP_LIST = """
SELECT DISTINCT Group_Name AS Group_Name,
       datetime(Message_Date / 1000, 'unixepoch', 'localtime') as Message_Date,
       Number_of_Messages
FROM (
    SELECT chat_view.subject AS Group_Name,
           chat_view.last_message_row_id,
           message.chat_row_id,
           message.timestamp as Message_Date
    FROM chat_view
    JOIN message ON chat_view.last_message_row_id = message._id
    LEFT JOIN jid ON chat_view.jid_row_id = jid._id
    WHERE jid.server = 'g.us'
) AS contact
JOIN (
    SELECT chat_row_id, COUNT(message._id) AS Number_of_Messages
    FROM message
    GROUP BY chat_row_id
) AS chat_count ON contact.chat_row_id = chat_count.chat_row_id
"""

GPS_LOCATIONS = """
SELECT CASE WHEN from_me == 1 THEN 'Database owner'
            ELSE CASE WHEN jid.server == 'g.us' THEN chat_view.subject ELSE jid.user END
       END AS Sender,
       CASE WHEN from_me == 0 THEN 'Database owner'
            ELSE CASE WHEN jid.server == 'g.us' THEN chat_view.subject ELSE jid.user END
       END AS Receiver,
       datetime(message.timestamp / 1000, 'unixepoch', 'localtime') AS MessageDate,
       message_location.latitude AS Latitude,
       message_location.longitude AS Longitude
FROM message_location
LEFT JOIN message ON message_location.message_row_id = message._id
LEFT JOIN chat_view ON message_location.chat_row_id = chat_view._id
LEFT JOIN jid ON chat_view.jid_row_id = jid._id
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
