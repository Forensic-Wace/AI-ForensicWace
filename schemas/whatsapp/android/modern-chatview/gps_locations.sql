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
