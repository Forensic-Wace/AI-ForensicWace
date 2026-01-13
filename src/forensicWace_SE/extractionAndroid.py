import plistlib
import os
import sqlite3
from datetime import datetime

import utils as utils
import globalConstants as globalConstants
from src.forensicWace_SE.repository import android_query
from src.forensicWace_SE.repository.msgstore_db import SQLiteDB

# Backup info file names
iosInfoFiles = {
    'manifest': 'Manifest.plist',
    'manifestDB': 'Manifest.db',
    'info': 'Info.plist',
    'status': 'Status.plist'
}


def GetIosDeviceExtractionList(deviceExtractionPath):
    """Gets the list of all devices backup extraction available in the system.
    The base folder is taken as input parameter.
    Returns a list of object of type device base info such as:
    - Udid
    - Device name
    - Device ios version
    - Device serial number
    - Device type
    - Backup date and time"""
    toReturnList = []

    if not os.path.exists(deviceExtractionPath):
        print(f"[GetDeviceExtractionList] - Path {deviceExtractionPath} does NOT exist")
        return toReturnList

    # Check if contains subfolders
    subfolders = [f.name for f in os.scandir(deviceExtractionPath) if f.is_dir()]

    if not subfolders:
        return toReturnList

    if deviceExtractionPath:
        (_, dirNames, _) = next(os.walk(deviceExtractionPath))

        for i in dirNames:
            GetDeviceBasicInfo(udid=i, path=deviceExtractionPath)
            toReturnList.append(GetDeviceBasicInfo(udid=i, path=deviceExtractionPath))

        return toReturnList
    else:
        raise Exception("Need valid backup root folder path passed through 'deviceExtractionPath'.")


def GetAndroidDeviceExtractionList(deviceExtractionPath):
    toReturnList = []

    if not os.path.exists(deviceExtractionPath):
        print(f"[GetDeviceExtractionList] - Path {deviceExtractionPath} does NOT exist")
        return toReturnList

    if deviceExtractionPath:
        # Check if contains subfolders
        subfolders = [f.name for f in os.scandir(deviceExtractionPath) if f.is_dir()]

        for subfolder in subfolders:
                db_files = [f for f in os.listdir(os.path.join(deviceExtractionPath, subfolder)) if f.endswith('.db')]
                for db_file in db_files:
                    db_file_path = os.path.join(deviceExtractionPath, subfolder, db_file)
                    file_size =  utils.GetFileSize(db_file_path)
                    readable_time = datetime.fromtimestamp(os.path.getctime(db_file_path)).strftime("%Y-%m-%d %H:%M:%S")
                    toReturnList.append({
                        'folderName': subfolder,
                        'fileName': db_file,
                        'fileSize':file_size,
                        'fileCreationDate': readable_time
                    })

        return toReturnList
    else:
        raise Exception("Need valid backup root folder path passed through 'deviceExtractionPath'.")


def GetDeviceBasicInfo(udid, path):
    """Gets the basic device information from the manifest file for a specific device Udid.
    Returns an object containing the basic device information.
    If the manifest file is not found, an empty object is returned."""
    if udid and path:
        manifestFile = os.path.join(path, udid, iosInfoFiles['manifest'])
        deviceBasicInfo = {}
        try:
            with open(manifestFile, 'rb') as infile:
                manifest = plistlib.load(infile)
        except FileNotFoundError:
            print(f"{udid} under {path} doesn't seem to have a manifest file.")
            return None
        deviceBasicInfo = {
            "udid": udid,
            "name": manifest['Lockdown']['DeviceName'],
            "ios": manifest['Lockdown']['ProductVersion'],
            "serial": manifest['Lockdown']['SerialNumber'],
            "type": manifest['Lockdown']['ProductType'],
            "date": utils.ConvertTime(os.path.getmtime(manifestFile), since2001=False),
        }
    else:
        raise Exception("Need valid backup root folder path and a device UDID.")

    return deviceBasicInfo


def ExecuteQuery(databasePath, query):
    """Connects to the database available in the input path and executes the input query.
    Returns the list of extracted data and an error message in case of fail."""

    extractedData = None
    errorMsg = None

    # Connect to the database
    conn = sqlite3.connect(databasePath)

    try:
        cursor = conn.cursor()
        results = cursor.execute(query)

        extractedData = [dict(zip([column[0] for column in cursor.description], row)) for row in results]

    except Exception as error:
        errorMsg = globalConstants.queryExecutionError

    conn.close()

    return extractedData, errorMsg


def GetChatList(basePath, backupInfo):
    """Returns a list of object containing the information about the list of available chats in the device backup.
    Returns also an error message in case an error occurs during extraction.
    The function takes the device UDID as input in order to select the correct database from which extract the infos."""
    query = globalConstants.queryChatList

    databasePath = basePath +"/" + globalConstants.deviceExtractions_FOLDER_ANDROID + "/" + backupInfo['android_folder_name'] + "/"+ backupInfo['AndroidFileName']
    databasePath = utils.normalize_path(databasePath)

    db = SQLiteDB(databasePath)
    db.connect()

    extractedData, errorMsg = ExecuteQuery(databasePath, globalConstants.queryChatList_Android)

    return extractedData, errorMsg


def GetPrivateChat(basePath, backupInfo, phoneNumber):

    databasePath = basePath +"/" + globalConstants.deviceExtractions_FOLDER_ANDROID + "/" + backupInfo['android_folder_name'] + "/"+ backupInfo['AndroidFileName']
    databasePath = utils.normalize_path(databasePath)

    countersQuery = globalConstants.queryPrivateChatCounters_Android.replace("{phoneNumber}", phoneNumber)

    chatCounters, errorMsg = ExecuteQuery(databasePath, countersQuery)

    chatDataQuery = globalConstants.queryPrivateChatMessages_Android.replace("{phoneNumber}", phoneNumber)

    messages, errorMsg = ExecuteQuery(databasePath, chatDataQuery)

    return chatCounters, messages, errorMsg


def GetGpsData(basePath, backupInfo):
    query = globalConstants.queryGpsData_Android

    databasePath = basePath + "/" + globalConstants.deviceExtractions_FOLDER_ANDROID + "/" + backupInfo['android_folder_name'] + "/" + backupInfo['AndroidFileName']

    extractedData, errorMsg = ExecuteQuery(databasePath, query)

    return extractedData, errorMsg


def GetBlockedContacts(basePath, deviceUdid):
    """Returns a list of object containing the information about the blocked contacts extracted from the device backup.
    Returns also an error message in case an error occurs during extraction.
    The function takes the device UDID as input in order to select the correct database from which extract the infos."""
    query = globalConstants.queryBlockedContacts

    databasePath = basePath + "/" + globalConstants.deviceExtractions_FOLDER + "/" + deviceUdid + globalConstants.defaultDatabase_PATH

    extractedData, errorMsg = ExecuteQuery(databasePath, query)

    return extractedData, errorMsg


def GetGroupList(basePath, backupInfo):

    databasePath = basePath +"/" + globalConstants.deviceExtractions_FOLDER_ANDROID + "/" + backupInfo['android_folder_name'] + "/"+ backupInfo['AndroidFileName']
    databasePath = utils.normalize_path(databasePath)

    db = SQLiteDB(databasePath)
    db.connect()

    extractedData, errorMsg = ExecuteQuery(databasePath, globalConstants.queryGroupList_Android)

    return extractedData, errorMsg


def GetGroupChat(basePath, deviceUdid, groupName):
    countersQuery = globalConstants.queryGroupChatCountersPT1 + groupName + globalConstants.queryGroupChatCountersPT2

    databasePath = basePath + "/" + globalConstants.deviceExtractions_FOLDER + "/" + deviceUdid + globalConstants.defaultDatabase_PATH

    chatCounters, errorMsg = ExecuteQuery(databasePath, countersQuery)

    chatDataQuery = globalConstants.queryGroupChatMessagesPT1 + groupName + globalConstants.queryGroupChatMessagesPT2

    messages, errorMsg = ExecuteQuery(databasePath, chatDataQuery)

    return chatCounters, messages, errorMsg


# noinspection SqlNoDataSourceInspection
def GetMediaFromBackup(basePath, deviceUdid, filePath, isChatMedia, isProfilePic):

    imagePath = None

    manifestDBFilePath = basePath + "/" + os.path.join(globalConstants.deviceExtractions_FOLDER, deviceUdid, globalConstants.manifestDBFile)

    with sqlite3.connect(manifestDBFilePath) as manifest:
        manifest.row_factory = sqlite3.Row
        c = manifest.cursor()
        if isChatMedia:
            filePath = 'Message/' + filePath
            c.execute(f"""SELECT fileID,
                                            relativePath,
                                            flags,
                                            ROW_NUMBER() OVER(ORDER BY relativePath) AS _index
                                    FROM Files
                                    WHERE
                                        domain = '{globalConstants.WhatsAppDomain}'
                                        AND relativePath LIKE '{filePath}'
                                    ORDER BY relativePath""")
        if isProfilePic:
            filePath = 'Media/Profile/%' + filePath + '%'
            c.execute(f"""SELECT fileID,
                                relativePath,
                                flags,
                                ROW_NUMBER() OVER(ORDER BY relativePath) AS _index
                        FROM Files
                        WHERE
                            domain = '{globalConstants.WhatsAppDomain}'
                            AND relativePath LIKE '{filePath}'
                            AND relativePath NOT LIKE '%-%-%'
                        ORDER BY relativePath DESC""")
        row = c.fetchone()
        while row is not None:
            if row["relativePath"] == "":
                row = c.fetchone()
                continue
            hashes = row["fileID"]
            folder = hashes[:2]
            flags = row["flags"]
            if flags == 1:
                imagePath = os.path.join(globalConstants.deviceExtractions_FOLDER, deviceUdid, folder, hashes)
                #print(imagePath) // Enable only for DEBUG purposes
                break
            row = c.fetchone()

    return imagePath
