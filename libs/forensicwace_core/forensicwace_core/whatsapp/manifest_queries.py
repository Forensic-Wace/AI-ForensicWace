"""Parameterized SQL for the iOS backup ``Manifest.db`` (file locator).

This is iTunes-backup plumbing, common to every WhatsApp version, so it lives
in code rather than in the versioned schema registry.
"""

CHAT_MEDIA = """
SELECT fileID, relativePath, flags
FROM Files
WHERE domain = :domain AND relativePath LIKE :path_pattern
ORDER BY relativePath
"""

PROFILE_PIC = """
SELECT fileID, relativePath, flags
FROM Files
WHERE domain = :domain
  AND relativePath LIKE :path_pattern
  AND relativePath NOT LIKE '%-%-%'
ORDER BY relativePath DESC
"""
