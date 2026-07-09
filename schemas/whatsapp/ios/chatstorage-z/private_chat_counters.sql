SELECT count(case when True then 1 else null end) as TotalMessages,
       count(case when ZWAMESSAGE.ZMESSAGETYPE = 14 then 1 else null end) as DeletedMessages,
       count(case when ZWAMESSAGE.ZMESSAGETYPE IN ('1','38','2','39','3','4','5','7','8') then 1 else null end) as Attachments,
       count(case when ZWAMESSAGE.ZMESSAGETYPE IN (1, 38) then 1 else null end) as Images,
       count(case when ZWAMESSAGE.ZMESSAGETYPE IN (2, 39) then 1 else null end) as Videos,
       count(case when ZWAMESSAGE.ZMESSAGETYPE = 3 then 1 else null end) as Audio,
       count(case when ZWAMESSAGE.ZMESSAGETYPE = 4 then 1 else null end) as Contacts,
       count(case when ZWAMESSAGE.ZMESSAGETYPE = 5 then 1 else null end) as Positions,
       count(case when ZWAMESSAGE.ZMESSAGETYPE = 15 then 1 else null end) as Stickers,
       count(case when ZWAMESSAGE.ZMESSAGETYPE = 7 then 1 else null end) as Url,
       count(case when ZWAMESSAGE.ZMESSAGETYPE = 8 then 1 else null end) as File
FROM (ZWAMESSAGE JOIN ZWACHATSESSION ON ZWAMESSAGE.ZCHATSESSION = ZWACHATSESSION.Z_PK)
LEFT JOIN ZWAMEDIAITEM ON ZWAMESSAGE.ZMEDIAITEM = ZWAMEDIAITEM.Z_PK
WHERE ZWACHATSESSION.ZCONTACTJID LIKE :jid_pattern AND ZSESSIONTYPE = 0
