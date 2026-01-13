# Folders Path
deviceExtractions_FOLDER_IOS = 'device_extractions_IOS'
deviceExtractions_FOLDER_ANDROID = 'device_extractions_Android'
assetsImage_FOLDER = 'assets/img'

# Files Path
defaultDatabase_PATH = '/7c/7c7fba66680ef796b916b067077cc246adacf01d'   # SQLite Database file is called by default '7c7fba66680ef796b916b067077cc246adacf01d' and it is stored under the '7c' folder inside the device backup
manifestDBFile = 'Manifest.db'

# WhatsApp variables
WhatsAppDomain = 'AppDomainGroup-group.net.whatsapp.WhatsApp.shared'

# Error variables
invalidPhoneNumber = "Invalid phone number"
infoNotAvailable = "Information not available"
notAvailable = "Not available"
missingReport = "Please select a PDF report"
missingCertificate = "Please select a TSR certificate"

# Error messages
invalidPhoneNumberErrorMsg = "The phone number you entered is INVALID, please try again"
queryExecutionError = "An ERROR occurred while executing the query"
apiSettingsNotSaved = "An ERROR occurred while saving the API settings"
Pay2UseSettingsNotSaved = "An ERROR occurred while saving the Pay to Use analyzer settings"

# Warning messages
chatFilterBaseMessage= "The Chat view is currently filtered to show only "

# Success messages
logoSuccessfullyChanged = "Logo successfully uploaded"
apiSettingsSuccessfullyChanged = "API settings successfully updated"
pay2UseSettingsSuccessfullyChanged = "Pay to Use analyzer settings successfully updated"

# Extraction Queries
queryChatList = "SELECT ZWACHATSESSION.ZPARTNERNAME AS Contact, ZWAPROFILEPUSHNAME.ZPUSHNAME AS UserName, SUBSTRING(ZJID, 1, 12) AS PhoneNumber, (SELECT COUNT(*) FROM ZWAMESSAGE WHERE ZWACHATSESSION.ZSESSIONTYPE == 0 AND ZMESSAGETYPE IN ('0','1','2','3','4','5','7','8','11','14','15','38','39') AND (ZFROMJID = ZWAPROFILEPUSHNAME.ZJID OR ZTOJID = ZWAPROFILEPUSHNAME.ZJID) ) AS NumberOfMessages, datetime(ZWAMESSAGE.ZMESSAGEDATE + 978307200, 'unixepoch') AS MessageDate FROM ZWACHATSESSION LEFT JOIN ZWAMESSAGE ON ZWACHATSESSION.ZLASTMESSAGE = ZWAMESSAGE.Z_PK LEFT JOIN ZWAPROFILEPUSHNAME ON ZWACHATSESSION.ZCONTACTJID = ZWAPROFILEPUSHNAME.ZJID WHERE ZWACHATSESSION.ZSESSIONTYPE == 0 AND ZJID IS NOT NULL GROUP BY ZWACHATSESSION.ZPARTNERNAME HAVING MAX(datetime(ZWAMESSAGE.ZMESSAGEDATE + 978307200, 'unixepoch')) AND NumberOfMessages > 0 ORDER BY CASE WHEN ZWACHATSESSION.ZPARTNERNAME LIKE '+%' THEN 1 ELSE 0 END ASC, ZWACHATSESSION.ZPARTNERNAME"
queryPrivateChatCountersPT1 = "SELECT count(case when True then 1 else null end) as TotalMessages, count(case when ZWAMESSAGE.ZMESSAGETYPE = 14 then 1 else null end) as DeletedMessages, count(case when ZWAMESSAGE.ZMESSAGETYPE IN ('1','38','2','39','3','4','5','7','8')  then 1 else null end) as Attachments, count(case when ZWAMESSAGE.ZMESSAGETYPE = 1 OR ZWAMESSAGE.ZMESSAGETYPE = 38 then 1 else null end) as Images, count(case when ZWAMESSAGE.ZMESSAGETYPE = 2 OR ZWAMESSAGE.ZMESSAGETYPE = 39 then 1 else null end) as Videos, count(case when ZWAMESSAGE.ZMESSAGETYPE = 3 then 1 else null end) as Audio, count(case when ZWAMESSAGE.ZMESSAGETYPE = 4 then 1 else null end) as Contacts, count(case when ZWAMESSAGE.ZMESSAGETYPE = 5 then 1 else null end) as Positions, count(case when ZWAMESSAGE.ZMESSAGETYPE = 15 then 1 else null end) as Stickers, count(case when ZWAMESSAGE.ZMESSAGETYPE = 7 then 1 else null end) as Url, count(case when ZWAMESSAGE.ZMESSAGETYPE = 8 then 1 else null end) as File FROM (ZWAMESSAGE JOIN ZWACHATSESSION ON ZWAMESSAGE.ZCHATSESSION = ZWACHATSESSION.Z_PK ) LEFT JOIN ZWAMEDIAITEM ON ZWAMESSAGE.ZMEDIAITEM=ZWAMEDIAITEM.Z_PK WHERE ZWACHATSESSION.ZCONTACTJID LIKE '%"
queryPrivateChatCountersPT2 = "%' AND ZSESSIONTYPE = 0 ORDER BY ZWAMESSAGE.ZSENTDATE ASC;"
queryPrivateChatMessagesPT1 = "SELECT SUBSTRING(ZFROMJID, 1, 12) as user, ZWAMESSAGE.ZTEXT as text, ZWACHATSESSION.ZPARTNERNAME as ZPARTNERNAME, ZWAMESSAGE.ZMESSAGETYPE as ZMESSAGETYPE, ZWAMESSAGEINFO.ZRECEIPTINFO as dateTimeInfos, datetime(ZWAMESSAGE.ZMESSAGEDATE + 978307200, 'unixepoch') as receiveDateTime, ZMOVIEDURATION as duration, ZLATITUDE as latitude, ZLONGITUDE as longitude, ZVCARDNAME as contactName, ZVCARDSTRING as vcardString, SUBSTR(ZWAMEDIAITEM.ZVCARDSTRING, INSTR(ZWAMEDIAITEM.ZVCARDSTRING, '/') + 1) as fileExtension, coalesce(ZWAMEDIAITEM.ZMEDIALOCALPATH, '') AS mediaPath FROM (ZWAMESSAGE JOIN ZWACHATSESSION ON ZWAMESSAGE.ZCHATSESSION = ZWACHATSESSION.Z_PK) LEFT JOIN ZWAMEDIAITEM ON ZWAMESSAGE.ZMEDIAITEM=ZWAMEDIAITEM.Z_PK LEFT JOIN ZWAMESSAGEINFO ON ZWAMESSAGEINFO.ZMESSAGE = ZWAMESSAGE.Z_PK WHERE ZWACHATSESSION.ZCONTACTJID LIKE '%"
queryPrivateChatMessagesPT2 = "%' AND ZWACHATSESSION.ZGROUPINFO is null AND ZMESSAGETYPE IN ('0','1','2','3','4','5','7','8','11','14','15','38','39') ORDER BY ZWAMESSAGE.ZSENTDATE ASC;"
queryGpsData = "SELECT CASE WHEN ZWAMESSAGE.ZGROUPMEMBER IS NOT NULL THEN SUBSTRING(ZWAGROUPMEMBER.ZMEMBERJID, 1, 12) WHEN ZWAMESSAGE.ZFROMJID IS NULL THEN 'Database owner'ELSE SUBSTRING(ZWAMESSAGE.ZFROMJID, 1, 12) END	AS Sender, CASE WHEN ZWAMESSAGE.ZTOJID IS NULL AND ZWAMESSAGE.ZGROUPMEMBER IS NULL THEN 'Database owner'WHEN ZWAMESSAGE.ZTOJID IS NULL AND ZWAMESSAGE.ZGROUPMEMBER IS NOT NULL THEN ZWACHATSESSION.ZPARTNERNAME ELSE SUBSTRING(ZWAMESSAGE.ZTOJID, 1, 12) END AS Receiver, datetime(ZWAMESSAGE.ZMESSAGEDATE + 978307200, 'unixepoch') AS MessageDate, ZLATITUDE AS Latitude, ZLONGITUDE AS Longitude FROM ZWAMESSAGE JOIN ZWACHATSESSION ON ZWACHATSESSION.Z_PK = ZWAMESSAGE.ZCHATSESSION LEFT JOIN ZWAMEDIAITEM ON ZWAMESSAGE.ZMEDIAITEM = ZWAMEDIAITEM.Z_PK LEFT JOIN ZWAGROUPMEMBER ON ZWAMESSAGE.ZGROUPMEMBER = ZWAGROUPMEMBER.Z_PK WHERE ZWAMESSAGE.ZMESSAGETYPE = 5 ORDER BY MessageDate"
queryBlockedContacts = "SELECT CASE WHEN ZPUSHNAME IS NULL THEN 'Name not available'ELSE ZPUSHNAME END	AS Name, SUBSTRING(ZWABLACKLISTITEM.ZJID, 1, 12) AS PhoneNumber FROM ZWABLACKLISTITEM LEFT JOIN ZWAPROFILEPUSHNAME ON ZWABLACKLISTITEM.ZJID = ZWAPROFILEPUSHNAME.ZJID"
queryGroupList = "SELECT ZPARTNERNAME AS Group_Name, datetime(ZWAMESSAGE.ZMESSAGEDATE + 978307200, 'unixepoch') AS Message_Date, (SELECT COUNT(*) FROM ZWAMESSAGE WHERE ZWAMESSAGE.ZMESSAGETYPE IN ('0','1','38','2','39','3','4','5','7','8','11','14','15','46') AND (ZWAMESSAGE.ZTOJID = ZWACHATSESSION.ZCONTACTJID OR ZWAMESSAGE.ZFROMJID = ZWACHATSESSION.ZCONTACTJID)) AS Number_of_Messages, ZWACHATPUSHCONFIG.ZMUTEDUNTIL AS Is_muted FROM ZWAMESSAGE LEFT JOIN ZWACHATSESSION ON ZWACHATSESSION.ZLASTMESSAGE = ZWAMESSAGE.Z_PK LEFT JOIN ZWAPROFILEPUSHNAME ON ZWACHATSESSION.ZCONTACTJID = ZWAPROFILEPUSHNAME.ZJID LEFT JOIN ZWACHATPUSHCONFIG ON ZWACHATPUSHCONFIG.ZJID = ZWACHATSESSION.ZCONTACTJID WHERE ZSESSIONTYPE = 1 ORDER BY ZWACHATSESSION.ZPARTNERNAME ASC"
queryGroupChatCountersPT1 = "SELECT count(case when ZWAMESSAGE.ZMESSAGETYPE IN ('0','1','38','2','39','3','4','5','7','8','11','14','15','46') then 1 else null end) as totalMessages, count(case when ZWAMESSAGE.ZMESSAGETYPE = 14 then 1 else null end) as deletedMessages, count(case when ZWAMESSAGE.ZMESSAGETYPE IN ('1','38','2','39','3','4','5','7','8')  then 1 else null end) as attachments, count(case when ZWAMESSAGE.ZMESSAGETYPE = 1 OR ZWAMESSAGE.ZMESSAGETYPE = 38 then 1 else null end) as images, count(case when ZWAMESSAGE.ZMESSAGETYPE = 2 OR ZWAMESSAGE.ZMESSAGETYPE = 39 then 1 else null end) as videos, count(case when ZWAMESSAGE.ZMESSAGETYPE = 3 then 1 else null end) as audio, count(case when ZWAMESSAGE.ZMESSAGETYPE = 4 then 1 else null end) as contacts, count(case when ZWAMESSAGE.ZMESSAGETYPE = 5 then 1 else null end) as positions, count(case when ZWAMESSAGE.ZMESSAGETYPE = 15 then 1 else null end) as stickers, count(case when ZWAMESSAGE.ZMESSAGETYPE = 7 then 1 else null end) as url, count(case when ZWAMESSAGE.ZMESSAGETYPE = 8 then 1 else null end) as file FROM ZWAMESSAGE join ZWACHATSESSION on ZWACHATSESSION.Z_PK=ZWAMESSAGE.ZCHATSESSION left JOIN ZWAMEDIAITEM ON ZWAMESSAGE.ZMEDIAITEM=ZWAMEDIAITEM.Z_PK left join ZWAGROUPMEMBER on ZWAMESSAGE.ZGROUPMEMBER=ZWAGROUPMEMBER.Z_PK WHERE ZWACHATSESSION.ZPARTNERNAME LIKE '%"
queryGroupChatCountersPT2 = "%'ORDER BY ZWAMESSAGE.ZSENTDATE ASC;"
queryGroupChatMessagesPT1 = "SELECT SUBSTRING(ZWAGROUPMEMBER.ZMEMBERJID, 1, 12) as user, CASE WHEN (SELECT CASE WHEN ZWACHATSESSION.ZPARTNERNAME IS NOT NULL THEN ZWACHATSESSION.ZPARTNERNAME ELSE ZWAPROFILEPUSHNAME.ZPUSHNAME END FROM ZWACHATSESSION LEFT JOIN ZWAPROFILEPUSHNAME ON ZWACHATSESSION.ZCONTACTJID = ZWAPROFILEPUSHNAME.ZJID WHERE ZJID LIKE ZWAGROUPMEMBER.ZMEMBERJID) IS NOT NULL THEN (SELECT CASE WHEN ZWACHATSESSION.ZPARTNERNAME IS NOT NULL THEN ZWACHATSESSION.ZPARTNERNAME ELSE ZWAPROFILEPUSHNAME.ZPUSHNAME END FROM ZWACHATSESSION LEFT JOIN ZWAPROFILEPUSHNAME ON ZWACHATSESSION.ZCONTACTJID = ZWAPROFILEPUSHNAME.ZJID WHERE ZJID LIKE ZWAGROUPMEMBER.ZMEMBERJID) WHEN ZWAGROUPMEMBER.ZMEMBERJID IS NULL THEN NULL ELSE 'Name not available' END AS contactName, ZWAMESSAGE.ZTEXT AS text, ZWAMESSAGE.ZMESSAGETYPE AS ZMESSAGETYPE, ZWAMESSAGEINFO.ZRECEIPTINFO as dateTimeInfos, datetime(ZWAMESSAGE.ZMESSAGEDATE + 978307200, 'unixepoch') AS receiveDateTime, ZMOVIEDURATION AS duration, ZLATITUDE AS latitude, ZLONGITUDE AS longitude, ZVCARDNAME AS vcardContactName, ZVCARDSTRING AS vcardString, SUBSTR(ZWAMEDIAITEM.ZVCARDSTRING, INSTR(ZWAMEDIAITEM.ZVCARDSTRING, '/') + 1) AS fileExtension, coalesce(ZWAMEDIAITEM.ZMEDIALOCALPATH, '') AS mediaPath FROM ZWAMESSAGE JOIN ZWACHATSESSION ON ZWACHATSESSION.Z_PK=ZWAMESSAGE.ZCHATSESSION LEFT JOIN ZWAMEDIAITEM ON ZWAMESSAGE.ZMEDIAITEM=ZWAMEDIAITEM.Z_PK LEFT join ZWAGROUPMEMBER ON ZWAMESSAGE.ZGROUPMEMBER=ZWAGROUPMEMBER.Z_PK LEFT JOIN ZWAMESSAGEINFO ON ZWAMESSAGEINFO.ZMESSAGE = ZWAMESSAGE.Z_PK WHERE ZWACHATSESSION.ZPARTNERNAME LIKE '%"
queryGroupChatMessagesPT2 = "%' AND ZMESSAGETYPE IN ('0','1','2','3','4','5','7','8','11','14','15','38','39') ORDER BY ZWAMESSAGE.ZSENTDATE ASC;"

queryChatList_Android='''SELECT SUBSTRING(PhoneNumber, 1, 12) AS PhoneNumber, datetime(MessageDate / 1000, 'unixepoch', 'localtime') as MessageDate, NumberOfMessages FROM (
    -- Otteniamo le informazioni di contatto e il messaggio associato
    SELECT jid.user AS PhoneNumber,
           chat_view.subject,
           chat_view.last_message_row_id,
           message.chat_row_id,
           message.timestamp  as MessageDate
    FROM chat_view
    JOIN message ON chat_view.last_message_row_id = message._id
    LEFT JOIN jid ON chat_view.jid_row_id = jid._id
	WHERE jid.server = "s.whatsapp.net"

) AS contact
JOIN (
    -- Contiamo i messaggi per ogni chat
    SELECT chat_row_id, COUNT(message._id) AS NumberOfMessages
    FROM message
    GROUP BY chat_row_id
) AS chat_count
ON contact.chat_row_id = chat_count.chat_row_id;'''



queryPrivateChatMessages_Android="""
SELECT _id, chat_row_id, from_me, 
       datetime(timestamp / 1000, 'unixepoch', 'localtime') AS readable_timestamp, 
       message_type, 
       text_data 
FROM message 
WHERE chat_row_id = (
    SELECT chat_view._id
    FROM jid
    INNER JOIN chat_view ON jid.raw_string = chat_view.raw_string_jid
    WHERE jid.user = {phoneNumber}
);"""

queryPrivateChatCounters_Android='''
SELECT
	   count(case when True then 1 else null end) as TotalMessages,
	   count(case when message_type = 15 then 1 else null end) as DeletedMessages,
	   count(case when message_type IN ('1','42','2','43','3','13','5','7','9') then 1 else null end) as Attachments, 
	   count(case when message_type = 1 OR message_type = 42 then 1 else null end) as Images,
	   count(case when message_type = 2 then 1 else null end) as Audio,
	   count(case when message_type = 3 OR message_type = 43 then 1 else null end) as Videos,
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
    WHERE jid.user LIKE '%{phoneNumber}%');
'''

queryGroupList_Android='''
SELECT DISTINCT Group_Name AS Group_Name, datetime(Message_Date / 1000, 'unixepoch', 'localtime') as Message_Date, Number_of_Messages FROM (
    -- Otteniamo le informazioni di contatto e il messaggio associato
    SELECT
           chat_view.subject AS Group_Name,
           chat_view.last_message_row_id,
           message.chat_row_id,
           message.timestamp  as Message_Date
    FROM chat_view
    JOIN message ON chat_view.last_message_row_id = message._id
    LEFT JOIN jid ON chat_view.jid_row_id = jid._id
	WHERE jid.server = "g.us"

) AS contact
JOIN (
    -- Contiamo i messaggi per ogni chat
    SELECT chat_row_id, COUNT(message._id) AS Number_of_Messages
    FROM message
    GROUP BY chat_row_id
) AS chat_count
ON contact.chat_row_id = chat_count.chat_row_id;'''

queryGpsData_Android='''
SELECT 
	CASE WHEN from_me == 1
		THEN 'Database owner'
		ELSE CASE WHEN  jid.server == 'g.us'
			THEN chat_view.subject
			ELSE jid.user
		END
	END AS Sender,
	CASE WHEN from_me == 0
		THEN 'Database owner'
		ELSE CASE WHEN  jid.server == 'g.us'
			THEN chat_view.subject
			ELSE jid.user
		END
	END AS Receiver,
	datetime(message.timestamp  / 1000, 'unixepoch', 'localtime') AS MessageDate,
	message_location.latitude AS Latitude,
	message_location.longitude AS Longitude

FROM message_location
LEFT JOIN message
ON message_location.message_row_id = message._id
LEFT JOIN chat_view
ON message_location.chat_row_id = chat_view._id
LEFT JOIN jid
on chat_view.jid_row_id = jid._id
'''

# View Mode for private chat
all = "All"
imageMediaType = 1
oneTimeImageMediaType = 38
videoMediaType = 2
oneTimeVideoMediaType = 39
audioMediaType = 3
contactMediaType = 4
positionMediaType = 5
urlMediaType = 7
fileMediaType = 8
gifMediaType = 11
deletedMessages = 14
stickerMediaType = 15
pollMediaType = 46

# Report name
GpsDataReport = "-GpsLocations"
ChatListReport = "-ChatList"
BlockedContactsReport = "-BlockedContacts"
GroupListReport = "-GroupList"
PrivateChat = "-PrivateChat-"
GroupChat = "-GroupChat-"

# Group notification status
Enabled = "ENABLED"
Disabled = "DISABLED"

# Strings for report
DeletedMessageInChatReport = "This message has been deleted by the sender"
NotAssigned = 'Not Assigned'
DatabaseOwner = 'Database Owner'

# Configuration file
ConfigurationFile = 'config.ini'
APIConfigurationSection = 'API'
Pay2UseAnalyzersConfigurationSection = 'Pay2UseAnalyzers'
OS_IOS = 'IOS'
OS_ANDROID = 'ANDROID'

expectedCheckboxesPay2UseAnalyzers = ['MsAzureOcrAndCaption', 'MsS2T', 'MsPii', 'OpenAiGpt']

testAudioContentS2T = 'This is an audio file to check the status of the speech to text service.'