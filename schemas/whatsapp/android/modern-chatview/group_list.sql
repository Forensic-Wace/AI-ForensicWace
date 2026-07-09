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
