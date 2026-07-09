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
