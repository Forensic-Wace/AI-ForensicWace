---
name: WhatsApp schema support
about: Report an unsupported WhatsApp database schema version
title: "[SCHEMA] "
labels: schema-support
---

## Platform

- [ ] Android (`msgstore.db`)
- [ ] iOS (`ChatStorage.sqlite`)

## WhatsApp version (if known)

<!-- e.g. 2.24.x -->

## Schema inventory

⚠️ **Structure only — never include row data, file contents, or personal information.**

Output of the following, run against the evidence DB **read-only**:

```sql
PRAGMA user_version;
SELECT name, type FROM sqlite_master WHERE type IN ('table','view') ORDER BY name;
```

For the message/chat-related tables, also include:

```sql
PRAGMA table_info(<table_name>);
```

```
(paste here)
```

## What fails

<!-- Which feature breaks (chat list, private chat, GPS, ...) and the error shown. -->
