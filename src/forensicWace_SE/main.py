import time
import uuid
from datetime import datetime
from typing import Dict

from flask import Flask, render_template, request, redirect, url_for, send_file

import os
import tempfile

# Import Custom Modules
import extractionIOS as extractionIOS
import extractionAndroid as extractionAndroid
import utils as utils
import globalConstants as globalConstants
import reporting as reporting

from src.forensicWace_SE.models.message import Messaggio
from src.forensicWace_SE.repository import android_query, text_repository
from src.forensicWace_SE.repository.database import SessionLocal
from src.forensicWace_SE.repository.models import ProcessStatus
from src.forensicWace_SE.repository.process_status_repository import get_process_status_all, update_process_status, \
    add_process_status, get_process_status
from src.forensicWace_SE.services import ExtractPiiService, starpii_Service, chatgptService, AudioServices, \
    deepPassClient, microsoftPIIExtractor, ImageServices
from src.forensicWace_SE.services.AudioServices import S2T
from src.forensicWace_SE.services.ImageServices import imageDesc
from src.forensicWace_SE.services.starpii_Service import starpii_extract
from src.forensicWace_SE.services.textServices import process_text

app = Flask(__name__, static_folder='/')

# Retrieve base Path
basePath = os.path.dirname(os.path.abspath(__file__))

# Configure each folder into the app
app.config['deviceExtractions_FOLDER_IOS'] = os.path.join(basePath, globalConstants.deviceExtractions_FOLDER_IOS)
app.config['deviceExtractions_FOLDER_ANDROID'] = os.path.join(basePath, globalConstants.deviceExtractions_FOLDER_ANDROID)

app.config['assetsImage_FOLDER'] = os.path.join(basePath, globalConstants.assetsImage_FOLDER)
app.config['systemTMP_FOLDER'] = tempfile.gettempdir()

# Dictionary to store all the variables and data for each connected host
hostsData = {}

# region Host Data Management
def AddOrUpdateHostData(hostId, data):
    """Creates or updates data for the host based on hostId.
    If hostId is NOT in the list then ADDs it to the list.
    If the hostId IS already in the list then UPDATE its values."""
    if hostId in hostsData:
        hostsData[hostId].update(data)
    else:
        hostsData[hostId] = data


def RemoveHostData(hostId):
    """Deletes all the data for the host based on hostId."""
    if hostId in hostsData:
        del (hostsData[hostId])
# endregion

# region  Route Definitions


# region / (index)
@app.route('/')
def Index():
    """Redirect the user to the index page to select a new backup extraction.
        Deletes all the data related to the hostId."""
    # Retrieve remote hostId
    clientId = request.remote_addr

    # Delete all data related to the remote host
    RemoveHostData(clientId)

    return render_template('index.html')

# endregion


# region /IosHomepage ()
@app.route('/IosHomepage')
def IosHomepage():
    # Retrieve remote hostId
    clientId = request.remote_addr

    if clientId in hostsData and hostsData[clientId].get('udid'):
        databasePath = basePath + "/" + globalConstants.deviceExtractions_FOLDER_IOS + "/" + hostsData[clientId][
            'udid'] + globalConstants.defaultDatabase_PATH
        databasePath = utils.normalize_path(databasePath)
        databaseSHA256 = utils.CalculateSHA256(databasePath)
        databaseMD5 = utils.CalculateMD5(databasePath)
        databaseSize = round(utils.GetFileSize(databasePath), 1)

        return render_template('homepage.html',
                               OS=hostsData[clientId]['OS'],
                               udid=hostsData[clientId]['udid'],
                               name=hostsData[clientId]['name'],
                               ios=hostsData[clientId]['ios'],
                               databaseSHA256=databaseSHA256,
                               databaseMD5=databaseMD5,
                               databaseSize=databaseSize,
                               OS_IOS = globalConstants.OS_IOS,
                               )
    else:
        availableDeviceExtractionList = extractionIOS.GetIosDeviceExtractionList(
            app.config['deviceExtractions_FOLDER_IOS'])
        return render_template('chooseIosBackup.html',
                               availableDeviceExtractionList=availableDeviceExtractionList,
                               numberOfAvailableDevicesExtractions=len(availableDeviceExtractionList),
                               url_for=url_for
                               )

# endregion

@app.route('/AndroidHomepage')
def AndroidHomepage():
    # Retrieve remote hostId
    clientId = request.remote_addr

    if clientId in hostsData and hostsData[clientId]['android_folder_name'] and hostsData[clientId]['AndroidFileName']:
        databasePath = basePath + "/" + globalConstants.deviceExtractions_FOLDER_ANDROID + "/" + hostsData[clientId][
            'android_folder_name'] + "/" + hostsData[clientId]['AndroidFileName']
        databasePath = utils.normalize_path(databasePath)
        databaseSHA256 = utils.CalculateSHA256(databasePath)
        databaseMD5 = utils.CalculateMD5(databasePath)
        databaseSize = round(utils.GetFileSize(databasePath), 1)

        AddOrUpdateHostData(clientId, {"OS": globalConstants.OS_ANDROID})

        return render_template('homepage.html',
                               OS=hostsData[clientId]['OS'],
                               databaseSHA256=databaseSHA256,
                               databaseMD5=databaseMD5,
                               databaseSize=databaseSize,
                               OS_IOS = globalConstants.OS_IOS,
                               )
    else:
        availableDeviceExtractionList = extractionIOS.GetAndroidDeviceExtractionList(
            app.config['deviceExtractions_FOLDER_ANDROID'])
        return render_template('chooseAndroidBackup.html',
                               availableDeviceExtractionList=availableDeviceExtractionList,
                               numberOfAvailableDevicesExtractions=len(availableDeviceExtractionList),
                               url_for=url_for
                               )

# endregion


# region / (ChooseIosBackup)
@app.route('/ChooseIosBackup')
def chooseIosBackup():

    # Retrieve remote hostId
    clientId = request.remote_addr
    AddOrUpdateHostData(clientId, {"OS":  globalConstants.OS_IOS})

    if clientId in hostsData and hostsData[clientId].get('udid'):
        databasePath = basePath + "/" + globalConstants.deviceExtractions_FOLDER_IOS + "/" + hostsData[clientId]['udid'] + globalConstants.defaultDatabase_PATH
        databasePath = utils.normalize_path(databasePath)
        databaseSHA256 = utils.CalculateSHA256(databasePath)
        databaseMD5 = utils.CalculateMD5(databasePath)
        databaseSize = round(utils.GetFileSize(databasePath), 1)

        return render_template('homepage.html',
                               OS=hostsData[clientId]['OS'],
                               udid=hostsData[clientId]['udid'],
                               name=hostsData[clientId]['name'],
                               ios=hostsData[clientId]['ios'],
                               databaseSHA256=databaseSHA256,
                               databaseMD5=databaseMD5,
                               databaseSize=databaseSize
                               )
    else:
        availableDeviceExtractionList = extractionIOS.GetIosDeviceExtractionList(
            app.config['deviceExtractions_FOLDER_IOS'])
        return render_template('chooseIosBackup.html',
                               availableDeviceExtractionList=availableDeviceExtractionList,
                               numberOfAvailableDevicesExtractions=len(availableDeviceExtractionList),
                               url_for=url_for
                               )
# endregion


# region / (ChooseAndroidBackup)
@app.route('/ChooseAndroidBackup')
def chooseAndroidBackup():

    # Retrieve remote hostId
    clientId = request.remote_addr

    if clientId not in hostsData:
        availableDeviceExtractionList = extractionIOS.GetAndroidDeviceExtractionList(
            app.config['deviceExtractions_FOLDER_ANDROID'])
        return render_template('chooseAndroidBackup.html',
                               availableDeviceExtractionList=availableDeviceExtractionList,
                               numberOfAvailableDevicesExtractions=len(availableDeviceExtractionList),
                               url_for=url_for
                               )
    else:
        databasePath = basePath + "/" + globalConstants.deviceExtractions_FOLDER_ANDROID + "/" + hostsData[clientId]['android_folder_name'] + "/"+ hostsData[clientId]['AndroidFileName']
        databasePath =  utils.normalize_path(databasePath)
        databaseSHA256 = utils.CalculateSHA256(databasePath)
        databaseMD5 = utils.CalculateMD5(databasePath)
        databaseSize = round(utils.GetFileSize(databasePath), 1)

        AddOrUpdateHostData(clientId, {"OS": globalConstants.OS_ANDROID})

        return render_template('homepage.html',
                               OS =hostsData[clientId]['OS'],
                               databaseSHA256=databaseSHA256,
                               databaseMD5=databaseMD5,
                               databaseSize=databaseSize
                               )
# endregion


# region ChooseExtraction
@app.route('/ChooseExtraction')
def ChooseExtraction():
    """Adds the information about the selected extracted backup to the system dictionary for the hostId."""
    clientId = request.remote_addr
    AddOrUpdateHostData(clientId, {"udid": request.args.get('udid')})
    AddOrUpdateHostData(clientId, {"name": request.args.get('name')})
    AddOrUpdateHostData(clientId, {"ios": request.args.get('ios')})
    AddOrUpdateHostData(clientId, {"messageType": "All"})
    AddOrUpdateHostData(clientId, {"OS": globalConstants.OS_IOS})
    return redirect(url_for('IosHomepage'))
# endregion

@app.route('/ChooseExtractionAndroid')
def ChooseExtractionAndroid():
    """Adds the information about the selected extracted backup to the system dictionary for the hostId."""
    clientId = request.remote_addr
    AddOrUpdateHostData(clientId, {"android_folder_name": request.args.get('android_folder_name')})
    AddOrUpdateHostData(clientId, {"AndroidFileName": request.args.get('AndroidFileName')})
    AddOrUpdateHostData(clientId, {"FileSize": request.args.get('FileSize')})
    AddOrUpdateHostData(clientId, {"messageType": "All"})
    AddOrUpdateHostData(clientId, {"OS": globalConstants.OS_ANDROID})
    return redirect(url_for('AndroidHomepage'))
# region Settings
@app.route('/Settings')
def Settings():
    configIniFile = utils.ReadConfigFile()

    analyzerStatuses = [
        AudioServices.check_status_Micosoft(),
        AudioServices.check_status_WhisperAI(),
        chatgptService.check_status(),
        deepPassClient.check_status(),
        ExtractPiiService.check_status(),
        microsoftPIIExtractor.check_status(),
        starpii_Service.check_status(),
        ImageServices.check_status_Microsoft(),
        ImageServices.check_status_LavisCaption(),
        ImageServices.check_status_TesseractOCR()
    ]

    return render_template('Settings.html', configIniFile=configIniFile, analyzerStatuses=analyzerStatuses)


@app.route('/ChangeLogo', methods=['GET', 'POST'])
def ChangeLogo():
    if request.method == 'POST':
        file = request.files['file']
        if file:
            # Create the file path and name
            filename = os.path.join(app.config['assetsImage_FOLDER'], 'Logo.png')
            # Save the received file in the Assets folder for images
            file.save(filename)
        return render_template('Settings.html', saveSucceded=True, saveMessage=globalConstants.logoSuccessfullyChanged)

    return render_template('Settings.html')

@app.route('/SaveAPISettings', methods=['GET', 'POST'])
def SaveAPISettings():
    if utils.WriteConfigFile(request.form.items(), globalConstants.APIConfigurationSection):
        configIniFile = utils.ReadConfigFile()
        return render_template('Settings.html', saveSucceded=True, saveMessage=globalConstants.apiSettingsSuccessfullyChanged, configIniFile=configIniFile)
    else:
        return render_template('Settings.html', errorOccurred=True, errorMessage=globalConstants.apiSettingsNotSaved)

@app.route('/SavePay2UseAnalyzerSettings', methods=['GET', 'POST'])
def SavePay2UseAnalyzerSettings():
    if utils.WriteConfigFile(request.form.items(), globalConstants.Pay2UseAnalyzersConfigurationSection):
        configIniFile = utils.ReadConfigFile()
        return render_template('Settings.html', saveSucceded=True, saveMessage=globalConstants.pay2UseSettingsSuccessfullyChanged, configIniFile=configIniFile)
    else:
        return render_template('Settings.html', errorOccurred=True, errorMessage=globalConstants.Pay2UseSettingsNotSaved)
# endregion
# endregion


# region Exit
@app.route('/Exit')
def Exit():
    """Redirect the user to the index page to select a new backup extraction.
    Deletes all the data related to the hostId."""
    # Retrieve remote hostId
    clientId = request.remote_addr

    # Delete all data related to the remote host
    RemoveHostData(clientId)

    return redirect(url_for('Index'))
# endregion


# region ChatList
@app.route('/ChatList')
def ChatList():
    errorMsg = None

    # Retrieve remote hostId
    clientId = request.remote_addr

    if clientId not in hostsData:
        return redirect(url_for('Index'))

    OS = hostsData[clientId]['OS']

    if clientId in hostsData and 'chatListData' in hostsData[clientId]:
        chatListData = hostsData[clientId]['chatListData']
    else:
        if OS == globalConstants.OS_IOS:
            chatListData, errorMsg = extractionIOS.GetChatList(basePath, hostsData[clientId]['udid'])
        elif OS == globalConstants.OS_ANDROID:
            chatListData, errorMsg = extractionAndroid.GetChatList(basePath, hostsData[clientId])

        AddOrUpdateHostData(clientId, {"chatListData": chatListData})

    if errorMsg:
        return render_template('chatList.html',
                               errorMsg=errorMsg,
                               chatListData=None,
                               formatPhoneNumber=utils.FormatPhoneNumberForPageTables,
                               OS = OS,
                               OS_IOS = globalConstants.OS_IOS)
    else:
        return render_template('chatList.html',
                               errorMsg=errorMsg,
                               chatListData=chatListData,
                               formatPhoneNumber=utils.FormatPhoneNumberForPageTables,
                               OS=OS,
                               OS_IOS=globalConstants.OS_IOS)

@app.route('/ExportChatList')
def ExportChatList():
    # Retrieve remote hostId
    clientId = request.remote_addr

    if clientId not in hostsData:
        return redirect(url_for('Index'))

    if clientId in hostsData and 'chatListData' in hostsData[clientId]:
        chatListData = hostsData[clientId]['chatListData']
    else:
        chatListData, errorMsg = extractionIOS.GetChatList(basePath, hostsData[clientId]['udid'])
        AddOrUpdateHostData(clientId, {"chatListData": chatListData})

    generatedReportZip = reporting.ExportChatList(hostsData[clientId]['udid'], chatListData)

    return send_file(generatedReportZip, as_attachment=True)
# endregion


# region InsertPhoneNumber
@app.route('/InsertPhoneNumber')
def InsertPhoneNumber():
    return render_template('insertPhoneNumber.html')
# endregion


# region PrivateChat
@app.route('/PrivateChat', methods=['POST'])
def PrivateChat():
    # Retrieve remote hostId
    clientId = request.remote_addr

    phoneNumber = request.form['phoneNumber']
    retrievedMessageType = request.form['messageType']
    if request.form['phoneNumber'] is None or request.form['phoneNumber'] == '':
        return render_template('insertPhoneNumber.html', errorMsg=globalConstants.invalidPhoneNumberErrorMsg)

    if clientId not in hostsData:
        return redirect(url_for('Index'))
    else:
        deviceUdid = hostsData[clientId]['udid']
        messageType = 0

        # Convert retrieved messageType from string to integer if is a number
        if retrievedMessageType != -1:
            if retrievedMessageType.isdigit():
                messageType = int(retrievedMessageType)

        chatCounters, messages, errorMsg = extractionIOS.GetPrivateChat(basePath, hostsData[clientId]['udid'], phoneNumber[-10:])  # phoneNumber[-10:] --> Pass the last 10 characters inserted

        userProfilePicPath = extractionIOS.GetMediaFromBackup(basePath, deviceUdid, phoneNumber[-10:], False, True)
        dbOwnerProfilePicPath = extractionIOS.GetMediaFromBackup(basePath, deviceUdid, 'Photo', False, True)

        warningFilteredMsg = None

        # Filter messages to view on the page
        if messageType is not None and messageType == globalConstants.imageMediaType:
            messages = [m for m in messages if m['ZMESSAGETYPE'] == globalConstants.imageMediaType or m['ZMESSAGETYPE'] == globalConstants.oneTimeImageMediaType]     # Images
            warningFilteredMsg = globalConstants.chatFilterBaseMessage + "IMAGES"
        elif messageType is not None and messageType == globalConstants.videoMediaType:
            messages = [m for m in messages if m['ZMESSAGETYPE'] == globalConstants.videoMediaType or m['ZMESSAGETYPE'] == globalConstants.oneTimeVideoMediaType]     # Video
            warningFilteredMsg = globalConstants.chatFilterBaseMessage + "VIDEOS"
        elif messageType is not None and messageType == globalConstants.audioMediaType:
            messages = [m for m in messages if m['ZMESSAGETYPE'] == globalConstants.audioMediaType]  # Audio
            warningFilteredMsg = globalConstants.chatFilterBaseMessage + "AUDIOS"
        elif messageType is not None and messageType == globalConstants.contactMediaType:
            messages = [m for m in messages if m['ZMESSAGETYPE'] == globalConstants.contactMediaType]  # Contact
            warningFilteredMsg = globalConstants.chatFilterBaseMessage + "CONTACTS"
        elif messageType is not None and messageType == globalConstants.positionMediaType:
            messages = [m for m in messages if m['ZMESSAGETYPE'] == globalConstants.positionMediaType]  # Position
            warningFilteredMsg = globalConstants.chatFilterBaseMessage + "POSITIONS"
        elif messageType is not None and messageType == globalConstants.urlMediaType:
            messages = [m for m in messages if m['ZMESSAGETYPE'] == globalConstants.urlMediaType]  # URLs
            warningFilteredMsg = globalConstants.chatFilterBaseMessage + "URLS"
        elif messageType is not None and messageType == globalConstants.fileMediaType:
            messages = [m for m in messages if m['ZMESSAGETYPE'] == globalConstants.fileMediaType]  # File
            warningFilteredMsg = globalConstants.chatFilterBaseMessage + "FILES"
        elif messageType is not None and messageType == globalConstants.gifMediaType:
            messages = [m for m in messages if m['ZMESSAGETYPE'] == globalConstants.gifMediaType]  # Gif
            warningFilteredMsg = globalConstants.chatFilterBaseMessage + "GIFS"
        elif messageType is not None and messageType == globalConstants.stickerMediaType:
            messages = [m for m in messages if m['ZMESSAGETYPE'] == globalConstants.stickerMediaType]  # Sticker
            warningFilteredMsg = globalConstants.chatFilterBaseMessage + "STICKERS"

        if phoneNumber == globalConstants.invalidPhoneNumber:
            return render_template('insertPhoneNumber.html',
                                   errorMsg=globalConstants.invalidPhoneNumberErrorMsg)
        else:
            return render_template('privateChat.html',
                                   phoneNumber=utils.FormatPhoneNumber(phoneNumber),
                                   unformattedPhoneNumber=phoneNumber,
                                   chatCounters=chatCounters,
                                   messages=messages,
                                   GetSentDateTime=utils.GetSentDateTime,
                                   GetReadDateTime=utils.GetReadDateTime,
                                   deviceUdid=deviceUdid,
                                   GetMediaFromBackup=extractionIOS.GetMediaFromBackup,
                                   userProfilePicPath=userProfilePicPath,
                                   dbOwnerProfilePicPath=dbOwnerProfilePicPath,
                                   str=str,
                                   imageMediaType=globalConstants.imageMediaType,
                                   videoMediaType=globalConstants.videoMediaType,
                                   audioMediaType=globalConstants.audioMediaType,
                                   contactMediaType=globalConstants.contactMediaType,
                                   positionMediaType=globalConstants.positionMediaType,
                                   stickerMediaType=globalConstants.stickerMediaType,
                                   urlMediaType=globalConstants.urlMediaType,
                                   fileMediaType=globalConstants.fileMediaType,
                                   warningFilteredMsg=warningFilteredMsg,
                                   VcardTelExtractor = utils.VcardTelExtractor,
                                   basePath = basePath
                                   )

@app.route('/AndroidPrivateChat', methods=['POST'])
def AndroidPrivateChat():
    # Retrieve remote hostId
    clientId = request.remote_addr

    phoneNumber = request.form['phoneNumber']
    retrievedMessageType = request.form['messageType']
    if request.form['phoneNumber'] is None or request.form['phoneNumber'] == '':
        return render_template('insertPhoneNumber.html', errorMsg=globalConstants.invalidPhoneNumberErrorMsg)

    if clientId not in hostsData:
        return redirect(url_for('Index'))
    else:
        OS = hostsData[clientId]['OS']

        messageType = 0
        # Convert retrieved messageType from string to integer if is a number
        if retrievedMessageType != -1:
            if retrievedMessageType.isdigit():
                messageType = int(retrievedMessageType)

        chatCounters, messages, errorMsg = extractionAndroid.GetPrivateChat(basePath, hostsData[clientId], phoneNumber[-10:])  # phoneNumber[-10:] --> Pass the last 10 characters inserted

        if phoneNumber == globalConstants.invalidPhoneNumber:
            return render_template('insertPhoneNumber.html',
                                   errorMsg=globalConstants.invalidPhoneNumberErrorMsg)
        else:
            return render_template('privateChat.html',
                                   phoneNumber=utils.FormatPhoneNumber(phoneNumber),
                                   unformattedPhoneNumber=phoneNumber,
                                   chatCounters=chatCounters,
                                   messages=messages,
                                   GetSentDateTime=utils.GetSentDateTime,
                                   GetReadDateTime=utils.GetReadDateTime,
                                   deviceUdid=000,
                                   GetMediaFromBackup=extractionIOS.GetMediaFromBackup,
                                   userProfilePicPath=None,
                                   dbOwnerProfilePicPath=None,
                                   str=str,
                                   imageMediaType=globalConstants.imageMediaType,
                                   videoMediaType=globalConstants.videoMediaType,
                                   audioMediaType=globalConstants.audioMediaType,
                                   contactMediaType=globalConstants.contactMediaType,
                                   positionMediaType=globalConstants.positionMediaType,
                                   stickerMediaType=globalConstants.stickerMediaType,
                                   urlMediaType=globalConstants.urlMediaType,
                                   fileMediaType=globalConstants.fileMediaType,
                                   warningFilteredMsg=None,
                                   VcardTelExtractor = utils.VcardTelExtractor,
                                   basePath = basePath
                                   )

@app.route('/ExportPrivateChat', methods=['POST'])
def ExportPrivateChat():
    # Retrieve remote hostId
    clientId = request.remote_addr

    if clientId not in hostsData:
        return redirect(url_for('Index'))
    else:
        deviceUdid = hostsData[clientId]['udid']

        phoneNumber = request.form['phoneNumber']

    if request.form['phoneNumber'] is None or request.form['phoneNumber'] == '':
        return render_template('insertPhoneNumber.html', errorMsg=globalConstants.invalidPhoneNumberErrorMsg)

    chatCounters, messages, errorMsg = extractionIOS.GetPrivateChat(basePath, deviceUdid, phoneNumber[-10:])  # phoneNumber[-10:] --> Pass the last 10 characters inserted

    generatedReportZip = reporting.PrivateChatReport(deviceUdid, phoneNumber, messages)

    return send_file(generatedReportZip, as_attachment=True)
# endregion


# region GpsLocations
@app.route('/GpsLocations')
def GpsLocations():
    # Retrieve remote hostId
    clientId = request.remote_addr

    if clientId not in hostsData:
        return redirect(url_for('Index'))

    OS = hostsData[clientId]['OS']

    if OS == globalConstants.OS_IOS:
        gpsData, errorMsg = extractionIOS.GetGpsData(basePath, hostsData[clientId]['udid'])
    elif OS == globalConstants.OS_ANDROID:
        gpsData, errorMsg = extractionAndroid.GetGpsData(basePath, hostsData[clientId])

    if errorMsg:
        return render_template('gpsLocations.html',
                               errorMsg=errorMsg,
                               gpsData=None,
                               formatPhoneNumber=utils.FormatPhoneNumberForPageTables)
    else:
        return render_template('gpsLocations.html',
                               errorMsg=errorMsg,
                               gpsData=gpsData,
                               formatPhoneNumber=utils.FormatPhoneNumberForPageTables)

@app.route('/ExportGpsLocations')
def ExportGpsLocations():
    # Retrieve remote hostId
    clientId = request.remote_addr

    if clientId not in hostsData:
        return redirect(url_for('Index'))

    gpsData, errorMsg = extractionIOS.GetGpsData(basePath, hostsData[clientId]['udid'])

    generatedReportZip = reporting.ExportGpsLocations(hostsData[clientId]['udid'], gpsData)

    return send_file(generatedReportZip, as_attachment=True)
    
# endregion


# region BlockedContacts
@app.route('/BlockedContacts')
def BlockedContacts():
    # Retrieve remote hostId
    clientId = request.remote_addr

    if clientId not in hostsData:
        return redirect(url_for('Index'))

    blockedContactsData, errorMsg = extractionIOS.GetBlockedContacts(basePath, hostsData[clientId]['udid'])

    if errorMsg:
        return render_template('blockedContacts.html',
                               errorMsg=errorMsg,
                               blockedContactsData=None,
                               formatPhoneNumber=utils.FormatPhoneNumberForPageTables)
    else:
        return render_template('blockedContacts.html',
                               errorMsg=errorMsg,
                               blockedContactsData=blockedContactsData,
                               formatPhoneNumber=utils.FormatPhoneNumberForPageTables)

@app.route('/ExportBlockedContacts')
def ExportBlockedContacts():
    # Retrieve remote hostId
    clientId = request.remote_addr

    if clientId not in hostsData:
        return redirect(url_for('Index'))

    blockedContactsData, errorMsg = extractionIOS.GetBlockedContacts(basePath, hostsData[clientId]['udid'])

    generatedReportZip = reporting.ExportBlockedContactsReport(hostsData[clientId]['udid'], blockedContactsData)

    return send_file(generatedReportZip, as_attachment=True)
# endregion


# region GroupList
@app.route('/GroupList')
def GroupList():
    errorMsg = None

    # Retrieve remote hostId
    clientId = request.remote_addr

    if clientId not in hostsData:
        return redirect(url_for('Index'))

    OS = hostsData[clientId]['OS']

    if clientId in hostsData and 'groupListData' in hostsData[clientId]:
        groupListData = hostsData[clientId]['groupListData']
    else:
        if OS == globalConstants.OS_IOS:
            groupListData, errorMsg = extractionIOS.GetGroupList(basePath, hostsData[clientId]['udid'])
        elif OS == globalConstants.OS_ANDROID:
            groupListData, errorMsg = extractionAndroid.GetGroupList(basePath, hostsData[clientId])

        AddOrUpdateHostData(clientId, {"groupListData": groupListData})

    if errorMsg is not None:
        return render_template('groupList.html',
                               errorMsg=errorMsg,
                               groupListData=None,
                               formatPhoneNumber=utils.FormatPhoneNumberForPageTables,
                               OS=OS,
                               OS_IOS = globalConstants.OS_IOS)
    else:
        return render_template('groupList.html',
                               errorMsg=errorMsg,
                               groupListData=groupListData,
                               formatPhoneNumber=utils.FormatPhoneNumberForPageTables,
                               OS=OS,
                               OS_IOS=globalConstants.OS_IOS)

@app.route('/ExportGroupList')
def ExportGroupList():
    # Retrieve remote hostId
    clientId = request.remote_addr

    if clientId not in hostsData:
        return redirect(url_for('Index'))

    if clientId in hostsData and 'groupListData' in hostsData[clientId]:
        groupListData = hostsData[clientId]['groupListData']

    else:
        groupListData, errorMsg = extractionIOS.GetGroupList(basePath, hostsData[clientId]['udid'])
        AddOrUpdateHostData(clientId, {"groupListData": groupListData})

    generatedReportZip = reporting.ExportGroupList(hostsData[clientId]['udid'], groupListData)

    return send_file(generatedReportZip, as_attachment=True)
# endregion


# region SelectGroup
@app.route('/SelectGroup')
def SelectGroup():
    errorMsg = None

    # Retrieve remote hostId
    clientId = request.remote_addr

    if clientId not in hostsData:
        return redirect(url_for('Index'))

    OS = hostsData[clientId]['OS']

    if clientId in hostsData and 'groupListData' in hostsData[clientId]:
        groupListData = hostsData[clientId]['groupListData']
    else:
        groupListData, errorMsg = extractionIOS.GetGroupList(basePath, hostsData[clientId]['udid'])
        AddOrUpdateHostData(clientId, {"groupListData": groupListData})

    if errorMsg:
        return render_template('selectGroup.html',
                               errorMsg=errorMsg,
                               groupListData=None,
                               formatPhoneNumber=utils.FormatPhoneNumberForPageTables,
                               OS = OS,
                               OS_IOS = globalConstants.OS_IOS)
    else:
        return render_template('selectGroup.html',
                               errorMsg=errorMsg,
                               groupListData=groupListData,
                               formatPhoneNumber=utils.FormatPhoneNumberForPageTables,
                               OS=OS,
                               OS_IOS=globalConstants.OS_IOS)
# endregion


# region GroupChat
@app.route('/GroupChat', methods=['POST'])
def GroupChat():
    # Retrieve remote hostId
    clientId = request.remote_addr

    if clientId not in hostsData:
        return redirect(url_for('Index'))
    else:
        deviceUdid = hostsData[clientId]['udid']

        groupName = request.form['groupName']
        retrievedMessageType = request.form['messageType']
        messageType = 0

        # Convert retrieved messageType from string to integer in is a number
        if retrievedMessageType.isdigit():
            messageType = int(retrievedMessageType)

        chatCounters, messages, errorMsg = extractionIOS.GetGroupChat(basePath, hostsData[clientId]['udid'], groupName)

        dbOwnerProfilePicPath = extractionIOS.GetMediaFromBackup(basePath, deviceUdid, 'Photo', False, True)

        warningFilteredMsg = None

        # Filter messages to view on the page
        if messageType is not None and messageType == globalConstants.imageMediaType:
            messages = [m for m in messages if m['ZMESSAGETYPE'] == globalConstants.imageMediaType or m['ZMESSAGETYPE'] == globalConstants.oneTimeImageMediaType]     # Images
            warningFilteredMsg = globalConstants.chatFilterBaseMessage + "IMAGES"
        elif messageType is not None and messageType == globalConstants.videoMediaType:
            messages = [m for m in messages if m['ZMESSAGETYPE'] == globalConstants.videoMediaType or m['ZMESSAGETYPE'] == globalConstants.oneTimeVideoMediaType]     # Video
            warningFilteredMsg = globalConstants.chatFilterBaseMessage + "VIDEOS"
        elif messageType is not None and messageType == globalConstants.audioMediaType:
            messages = [m for m in messages if m['ZMESSAGETYPE'] == globalConstants.audioMediaType]  # Audio
            warningFilteredMsg = globalConstants.chatFilterBaseMessage + "AUDIOS"
        elif messageType is not None and messageType == globalConstants.contactMediaType:
            messages = [m for m in messages if m['ZMESSAGETYPE'] == globalConstants.contactMediaType]  # Contact
            warningFilteredMsg = globalConstants.chatFilterBaseMessage + "CONTACTS"
        elif messageType is not None and messageType == globalConstants.positionMediaType:
            messages = [m for m in messages if m['ZMESSAGETYPE'] == globalConstants.positionMediaType]  # Position
            warningFilteredMsg = globalConstants.chatFilterBaseMessage + "POSITIONS"
        elif messageType is not None and messageType == globalConstants.urlMediaType:
            messages = [m for m in messages if m['ZMESSAGETYPE'] == globalConstants.urlMediaType]  # URLs
            warningFilteredMsg = globalConstants.chatFilterBaseMessage + "URLS"
        elif messageType is not None and messageType == globalConstants.fileMediaType:
            messages = [m for m in messages if m['ZMESSAGETYPE'] == globalConstants.fileMediaType]  # File
            warningFilteredMsg = globalConstants.chatFilterBaseMessage + "FILES"
        elif messageType is not None and messageType == globalConstants.gifMediaType:
            messages = [m for m in messages if m['ZMESSAGETYPE'] == globalConstants.gifMediaType]  # Gif
            warningFilteredMsg = globalConstants.chatFilterBaseMessage + "GIFS"
        elif messageType is not None and messageType == globalConstants.stickerMediaType:
            messages = [m for m in messages if m['ZMESSAGETYPE'] == globalConstants.stickerMediaType]  # Sticker
            warningFilteredMsg = globalConstants.chatFilterBaseMessage + "STICKERS"

        return render_template('groupChat.html',
                               groupName=groupName,
                               chatCounters=chatCounters,
                               messages=messages,
                               GetSentDateTime=utils.GetSentDateTime,
                               GetReadDateTime=utils.GetReadDateTime,
                               deviceUdid=deviceUdid,
                               GetMediaFromBackup=extractionIOS.GetMediaFromBackup,
                               dbOwnerProfilePicPath=dbOwnerProfilePicPath,
                               str=str,
                               imageMediaType=globalConstants.imageMediaType,
                               videoMediaType=globalConstants.videoMediaType,
                               audioMediaType=globalConstants.audioMediaType,
                               contactMediaType=globalConstants.contactMediaType,
                               positionMediaType=globalConstants.positionMediaType,
                               stickerMediaType=globalConstants.stickerMediaType,
                               urlMediaType=globalConstants.urlMediaType,
                               fileMediaType=globalConstants.fileMediaType,
                               warningFilteredMsg=warningFilteredMsg,
                               formatPhoneNumber=utils.FormatPhoneNumberForPageTables,
                               vcardTelExtractor=utils.VcardTelExtractor,
                               basePath = basePath
                               )


@app.route('/ExportGroupChat', methods=['POST'])
def ExportGroupChat():
    # Retrieve remote hostId
    clientId = request.remote_addr

    if clientId not in hostsData:
        return redirect(url_for('Index'))
    else:
        deviceUdid = hostsData[clientId]['udid']
        groupName = request.form['groupName']

    if request.form['groupName'] is None or request.form['groupName'] == '':
        return render_template('selectGroup.html')

    chatCounters, messages, errorMsg = extractionIOS.GetGroupChat(basePath, deviceUdid, groupName)

    generatedReportZip = reporting.GroupChatReport(deviceUdid, groupName, messages)

    return send_file(generatedReportZip, as_attachment=True)

# endregion


# region CheckReport
@app.route('/CheckReport', methods=['GET', 'POST'])
def CheckReport():
    reportStatus = 0

    if request.method == 'POST':
        report = request.files['report']
        if report:
            # Create the file path and name
            reportPath = os.path.join(app.config['systemTMP_FOLDER'], report.filename)
            # Save the received file in the system TMP folder
            report.save(reportPath)
        else:
            return render_template('checkReport.html',
                                   reportStatus=None,
                                   errorMessage = globalConstants.missingReport)

        certificate = request.files['certificate']
        if certificate:
            # Create the file path and name
            certificatePath = os.path.join(app.config['systemTMP_FOLDER'], certificate.filename)
            # Save the received file in the system TMP folder
            certificate.save(certificatePath)
        else:
            return render_template('checkReport.html',
                                   reportStatus=None,
                                   errorMessage=globalConstants.missingCertificate)

        reportStatus = reporting.ReportCheckAuth(reportPath, certificatePath)

        os.remove(reportPath)
        os.remove(certificatePath)

    return render_template('checkReport.html',
                           reportStatus=reportStatus,
                           errorMessage = None)
# endregion


# region DiscoverMore
@app.route('/DiscoverMore')
def DiscoverMore():
    return render_template('discoverMore.html')
# endregion

# region /AIAnalyser
@app.route('/AIAnalyzer')
def AIAnalyzer():
    # Retrieve remote hostId
    clientId = request.remote_addr

    if clientId not in hostsData:
        return redirect(url_for('Index'))

    OS = hostsData[clientId]['OS']

    if clientId in hostsData and 'chatListData' in hostsData[clientId]:
        chatListData = hostsData[clientId]['chatListData']
        groupListData = hostsData[clientId]['groupListData']
    else:
        if OS == globalConstants.OS_IOS:
            chatListData, errorMsg = extractionIOS.GetChatList(basePath, hostsData[clientId]['udid'])
            groupListData, errorMsg = extractionIOS.GetGroupList(basePath, hostsData[clientId]['udid'])
        elif OS == globalConstants.OS_ANDROID:
            chatListData, errorMsg = extractionAndroid.GetChatList(basePath, hostsData[clientId])
            groupListData, errorMsg = extractionAndroid.GetGroupList(basePath, hostsData[clientId])

        AddOrUpdateHostData(clientId, {"chatListData": chatListData})
        AddOrUpdateHostData(clientId, {"groupListData": groupListData})

    configIniFile = utils.ReadConfigFile()

    useMsPii = True if configIniFile['Pay2UseAnalyzers']['mspii'] == 'on' else False
    useOpenaiGpt = True if configIniFile['Pay2UseAnalyzers']['openaigpt'] == 'on' else False

    return render_template('AIAnalyzer.html',
                           chatListData=chatListData,
                           groupListData=groupListData,
                           OS=OS,
                           OS_IOS=globalConstants.OS_IOS,
                           OS_ANDROID=globalConstants.OS_ANDROID,
                           useMsPii=useMsPii,
                           useOpenaiGpt=useOpenaiGpt)
# endregion

# endregion

from multiprocessing import Process
# Dizionario per memorizzare lo stato dei processi
process_status: Dict[str, Dict[str, str]] = {}

@app.route('/AnalizeChat', methods=['POST'])
def AnalizeChat():
    '''
    # Retrieve remote hostId
    clientId = request.remote_addr

    if clientId not in hostsData:
        return redirect(url_for('Index'))
    else:
        deviceUdid = hostsData[clientId]['udid']
        groupName = request.form['groupName']

    if request.form['groupName'] is None or request.form['groupName'] == '':
        return
    '''

    clientId = request.remote_addr

    if clientId not in hostsData:
        return redirect(url_for('Index'))

    OS = hostsData[clientId]['OS']
    databasePath = ""

    if OS == globalConstants.OS_IOS:
        databasePath = basePath + "/" + globalConstants.deviceExtractions_FOLDER_IOS + "/" + hostsData[clientId]['udid'] + globalConstants.defaultDatabase_PATH
    elif OS == globalConstants.OS_ANDROID:
        databasePath = basePath + "/" + globalConstants.deviceExtractions_FOLDER_ANDROID + "/" + hostsData[clientId][
            'android_folder_name'] + "/" + hostsData[clientId]['AndroidFileName']
        databasePath = utils.normalize_path(databasePath)


    process_id = str(uuid.uuid4())
    start_time = datetime.now()

    processInfo = ProcessStatus()

    processInfo.process_id = process_id
    processInfo.OS = OS
    processInfo.extraction_name_udid = hostsData[clientId]['android_folder_name']
    processInfo.db_path = databasePath
    processInfo.start_time = start_time.isoformat()
    processInfo.status = 'Started'
    processInfo.details = 'Process is started'
    processInfo.date_to = datetime.strptime(request.form['date_to'], "%Y-%m-%dT%H:%M")
    processInfo.date_from = datetime.strptime(request.form['date_from'], "%Y-%m-%dT%H:%M")
    processInfo.received = 1 if 'received' in request.form else 0
    processInfo.sent = 1 if 'sent' in request.form else 0
    processInfo.contacts = ','.join(request.form.getlist('contacts'))
    processInfo.groups = ','.join(request.form.getlist('groups'))
    processInfo.msg_type = ','.join(request.form.getlist('msg_type'))
    processInfo.analyzers = ','.join(request.form.getlist('analyzers'))

    add_process_status(processInfo)

    print(request.form['date_to'])
    process = Process(target=analize_chat_process, args=(processInfo.process_id,))
    process.start()
    #capire se mandare una pagina diretta o un solo messaggio
    #return f'Processo {process_id} avviato in background!'

    return redirect(url_for('ProcessesList'))

def background_process(arg, process_status):
    # Processo lungo o intensivo
    for i in range(arg):
        print(f"Esecuzione processo {i + 1}")
        time.sleep(1)

def analize_chat_process(processId):

    session = SessionLocal

    process = session.query(ProcessStatus).filter_by(process_id=processId).first()

    OS = process.OS
    message_list = ""
    if OS == globalConstants.OS_IOS:

        pass
    elif OS == globalConstants.OS_ANDROID:
        android_message_list= android_query.getMessagesDB(process.db_path,
                                                          process.date_from,
                                                          process.date_to,
                                                          process.received,
                                                          process.sent,
                                                          process.contacts.split(','),
                                                          process.groups.split(','),
                                                          process.msg_type.split(','))

        message_list = Messaggio.Android_2_MessageList(android_message_list,
                                                       process.extraction_name_udid)
        print(message_list)

    messages_len = len(message_list)
    for idx,message in enumerate(message_list):
        if 'S2T' in  process.analyzers.split(','):
            if message.audio_path:
                S2T(message)

        if 'image_OCR' in process.analyzers.split(','):
            if message.image_path:
               imageDesc(message)

        if message.text is not None:
            process_text(message, process.process_id, process.analyzers.split(','))
        print(message)

        process.status = 'Analyzing'
        process.details = f'Analized {idx + 1} over {messages_len} messages'

        update_process_status(process)

    process.status = 'Finish'
    process.details = f'Analized all messages'

    end_time = datetime.now()
    process.end_time = end_time.isoformat()

    update_process_status(process)

# region ProcessesList
@app.route('/ProcessesList')
def ProcessesList():
    process_status = get_process_status_all()

    activeProcesses = sum(1 for obj in process_status if obj.status == "Started" or obj.status == "Analyzing")
    finishedProcesses = sum(1 for obj in process_status if obj.status == "Finish")
    return render_template('processesList.html', numOfProcesses=len(process_status), process_status=process_status, activeProcesses=activeProcesses, finishedProcesses=finishedProcesses)

@app.route('/AIProcessResult', methods=['POST'])
def AIProcessResult():
    if request.form['aiProcessResult'] is None or request.form['aiProcessResult'] == '':
        return redirect(url_for('ProcessesList'))
    else:
        textList = text_repository.get_texts_by_process_id(request.form['aiProcessResult'])
        process = get_process_status(request.form['aiProcessResult'])

        OS = process.OS
        message_list = ""
        if OS == globalConstants.OS_IOS:

            pass
        elif OS == globalConstants.OS_ANDROID:
            android_message_list = android_query.getMessagesDB(process.db_path,
                                                               process.date_from,
                                                               process.date_to,
                                                               process.received,
                                                               process.sent,
                                                               process.contacts.split(','),
                                                               process.groups.split(','),
                                                               process.msg_type.split(','))

            message_list = Messaggio.Android_2_MessageList(android_message_list,
                                                           process.extraction_name_udid)
        rich_text_list= arricchisci_text_con_messaggi(textList,message_list)

        return render_template('AIAnalysisResult.html',
                               processId=request.form['aiProcessResult'],
                               numberOfMessages=len(rich_text_list),
                               textList=rich_text_list,
                               str=str)


def arricchisci_text_con_messaggi(lista_text, lista_messaggi):
    # Creiamo un dizionario dagli oggetti Messaggio per un accesso rapido
    messaggi_dict = {str(msg.id_messaggio): msg for msg in lista_messaggi}
    for text in lista_text:
        # Troviamo il messaggio corrispondente
        messaggio_correlato = messaggi_dict.get(str(text.msg_id))

        if messaggio_correlato:
            # Aggiungiamo dinamicamente tutte le proprietà di Messaggio a Text
            for attr, value in vars(messaggio_correlato).items():
                if attr != "text":
                    setattr(text, attr, value)

    return lista_text



# endregion

def main():
    """Defines the main function of the application."""
    app.config["DEBUG"] = True
    app.run(host='0.0.0.0', port=8000, debug=True)

if __name__ == '__main__':
    main()
