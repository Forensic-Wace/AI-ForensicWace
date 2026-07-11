"""Dynamically assembled iOS queries (analysis message selection).

The static extraction queries live in the schema registry
(``schemas/whatsapp/ios/...``). These helpers are templates whose IN clauses
are sized per request; the placeholders are always bound parameters.
"""

# 1:1 sessions matched by the contact's JID (last-10-digits pattern, one query
# per contact — LIKE patterns cannot share an IN clause).
PRIVATE_SESSION_BY_JID = """
SELECT Z_PK, ZPARTNERNAME
FROM ZWACHATSESSION
WHERE ZGROUPINFO IS NULL AND ZCONTACTJID LIKE ?
"""

GROUP_SESSIONS_BY_NAME = """
SELECT Z_PK, ZPARTNERNAME
FROM ZWACHATSESSION
WHERE ZGROUPINFO IS NOT NULL AND ZPARTNERNAME IN ({placeholders})
"""

# Message selection; media metadata joined in one pass. ZVCARDSTRING doubles
# as the MIME type on media items in this schema generation.
MESSAGES_BASE = """
SELECT m.Z_PK AS id,
       m.ZCHATSESSION AS chat_id,
       m.ZFROMJID AS from_jid,
       m.ZMESSAGEDATE AS message_date,
       m.ZMESSAGETYPE AS message_type,
       m.ZTEXT AS text,
       media.ZMEDIALOCALPATH AS media_local_path,
       media.ZVCARDSTRING AS media_meta
FROM ZWAMESSAGE m
LEFT JOIN ZWAMEDIAITEM media ON m.ZMEDIAITEM = media.Z_PK
WHERE m.ZCHATSESSION IN ({placeholders})
"""
