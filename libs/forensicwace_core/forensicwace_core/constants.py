"""Domain constants shared across the platform."""

from enum import StrEnum


class Platform(StrEnum):
    IOS = "ios"
    ANDROID = "android"


# iOS ZWAMESSAGE.ZMESSAGETYPE values
class IosMessageType:
    TEXT = 0
    IMAGE = 1
    VIDEO = 2
    AUDIO = 3
    CONTACT = 4
    POSITION = 5
    GROUP_EVENT = 6
    URL = 7
    FILE = 8
    GIF = 11
    DELETED = 14
    STICKER = 15
    ONE_TIME_IMAGE = 38
    ONE_TIME_VIDEO = 39
    POLL = 46


# All the message types the UI knows how to render.
IOS_SUPPORTED_MESSAGE_TYPES = (0, 1, 2, 3, 4, 5, 7, 8, 11, 14, 15, 38, 39)

# Message-type filters accepted by the private/group chat endpoints.
# Values are tuples because "images" also matches one-time-view images, etc.
IOS_MESSAGE_TYPE_FILTERS: dict[str, tuple[int, ...]] = {
    "images": (IosMessageType.IMAGE, IosMessageType.ONE_TIME_IMAGE),
    "videos": (IosMessageType.VIDEO, IosMessageType.ONE_TIME_VIDEO),
    "audios": (IosMessageType.AUDIO,),
    "contacts": (IosMessageType.CONTACT,),
    "positions": (IosMessageType.POSITION,),
    "urls": (IosMessageType.URL,),
    "files": (IosMessageType.FILE,),
    "gifs": (IosMessageType.GIF,),
    "stickers": (IosMessageType.STICKER,),
}

# Android message.message_type values -> logical type
ANDROID_MESSAGE_TYPES: dict[int, str] = {
    0: "text",
    1: "image",
    42: "image",
    2: "audio",
    3: "video",
    43: "video",
    13: "gif",
    5: "location",
    6: "groupEvent",
    7: "url",
    9: "file",
}

# Logical type -> Android message.message_type values (for query filters)
ANDROID_TYPE_CODES: dict[str, tuple[int, ...]] = {
    "text": (0,),
    "image": (1, 42),
    "audio": (2,),
    "video": (3, 43),
    "gif": (13,),
    "location": (5,),
    "groupEvent": (6,),
    "url": (7,),
    "file": (9,),
}

# iOS backup internals
IOS_CHATSTORAGE_RELATIVE_PATH = ("7c", "7c7fba66680ef796b916b067077cc246adacf01d")
IOS_MANIFEST_DB = "Manifest.db"
IOS_MANIFEST_PLIST = "Manifest.plist"
WHATSAPP_IOS_DOMAIN = "AppDomainGroup-group.net.whatsapp.WhatsApp.shared"

DATABASE_OWNER = "Database owner"
DELETED_MESSAGE_TEXT = "This message has been deleted by the sender"
INFO_NOT_AVAILABLE = "Information not available"
