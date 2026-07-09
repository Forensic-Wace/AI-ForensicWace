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
