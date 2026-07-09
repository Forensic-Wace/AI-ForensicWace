SELECT count(case when ZWAMESSAGE.ZMESSAGETYPE IN ('0','1','38','2','39','3','4','5','7','8','11','14','15','46') then 1 else null end) as totalMessages,
       count(case when ZWAMESSAGE.ZMESSAGETYPE = 14 then 1 else null end) as deletedMessages,
       count(case when ZWAMESSAGE.ZMESSAGETYPE IN ('1','38','2','39','3','4','5','7','8') then 1 else null end) as attachments,
       count(case when ZWAMESSAGE.ZMESSAGETYPE IN (1, 38) then 1 else null end) as images,
       count(case when ZWAMESSAGE.ZMESSAGETYPE IN (2, 39) then 1 else null end) as videos,
       count(case when ZWAMESSAGE.ZMESSAGETYPE = 3 then 1 else null end) as audio,
       count(case when ZWAMESSAGE.ZMESSAGETYPE = 4 then 1 else null end) as contacts,
       count(case when ZWAMESSAGE.ZMESSAGETYPE = 5 then 1 else null end) as positions,
       count(case when ZWAMESSAGE.ZMESSAGETYPE = 15 then 1 else null end) as stickers,
       count(case when ZWAMESSAGE.ZMESSAGETYPE = 7 then 1 else null end) as url,
       count(case when ZWAMESSAGE.ZMESSAGETYPE = 8 then 1 else null end) as file
FROM ZWAMESSAGE
JOIN ZWACHATSESSION ON ZWACHATSESSION.Z_PK = ZWAMESSAGE.ZCHATSESSION
LEFT JOIN ZWAMEDIAITEM ON ZWAMESSAGE.ZMEDIAITEM = ZWAMEDIAITEM.Z_PK
LEFT JOIN ZWAGROUPMEMBER ON ZWAMESSAGE.ZGROUPMEMBER = ZWAGROUPMEMBER.Z_PK
WHERE ZWACHATSESSION.ZPARTNERNAME LIKE :group_pattern
