import os
import subprocess

import requests

from src.forensicWace_SE import utils, globalConstants

configIniFile = utils.ReadConfigFile()

MS_S2T_key = configIniFile['API']['mss2tkey']
MS_S2T_region = configIniFile['API']['mss2tregion']
MS_S2T_language = configIniFile['API']['mss2tlanguage']
whisperEndpoint = configIniFile['API']['audios2twhisperaserendpoint']

useMsS2T = True if configIniFile['Pay2UseAnalyzers']['mss2t'] == 'on' else False

import azure.cognitiveservices.speech as speechsdk

if useMsS2T and MS_S2T_key != '' and MS_S2T_region != '' and MS_S2T_language != '':
    speech_config = speechsdk.SpeechConfig(subscription=MS_S2T_key, region=MS_S2T_region)
    speech_config.speech_recognition_language = MS_S2T_language

def check_status_Micosoft():
    if useMsS2T:
        if isinstance(MS_S2T_key, str):
            print("Valid MS_S2T_key token")
            if isinstance(MS_S2T_region, str):
                print("Valid MS_S2T_region")
                if isinstance(MS_S2T_language, str):
                    print("Valid MS_S2T_language")
                    try:
                        basePath = os.path.dirname(os.path.abspath(__file__))
                        testAudioPath = basePath + "/AnalyzerAvailabilityCheckResources/TestAvailabilityS2T.wav"
                        audio_config = speechsdk.AudioConfig(filename=testAudioPath)
                        speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config,
                                                                       audio_config=audio_config)

                        result = speech_recognizer.recognize_once_async().get()

                        if result.text.strip().lower() == globalConstants.testAudioContentS2T.lower():
                            return True, "MS_S2T", "MS_S2T is working"
                        else:
                            return False, "MS_S2T", "MS_S2T conversion did not match input audio content"
                    except Exception as e:
                        print(e)
                        return False, "MS_S2T", e
                else:
                    print("Invalid MS_S2T_language")
                    return False, "MS_S2T", "Invalid MS_S2T_language"
            else:
                print("Invalid MS_S2T_region")
                return False, "MS_S2T", "Invalid MS_S2T_region"
        else:
            print("Unvalid Azure Token")
            return False, "MS_S2T", "Invalid Azure Token"
    else:
        return False, "MS_S2T", "Microsoft Service not selected"

def check_status_WhisperAI():
    if whisperEndpoint is not None or whisperEndpoint != '':
        print("WhisperAI endpoint token available")
        try:
            basePath = os.path.dirname(os.path.abspath(__file__))
            testAudioPath = basePath + "/AnalyzerAvailabilityCheckResources/TestAvailabilityS2T.wav"

            files = {
                "audio_file": ("audio", open(testAudioPath, "rb"), "audio/wav")
            }

            headers = {
                "accept": "application/json"
            }

            params = {
                "encode": str(True).lower(),  # true/false in lowercase
                "task": "transcribe",
                "output": "txt"
            }

            response = requests.post(whisperEndpoint, headers=headers, files=files, params=params)

            if response.text.strip().lower() == globalConstants.testAudioContentS2T.lower():
                return True, "WhisperAI", "WhisperAI is working"
            else:
                return False, "WhisperAI", "WhisperAI conversion did not match input audio content"
        except Exception as e:
            print(e)
            return False, "WhisperAI", e
    else:
        print("Invalid WhisperAI endpoint")
        return False, "WhisperAI", "Invalid WhisperAI endpoint"

def S2T(message):
    output_path=''
    if 'opus' in message.mime_type or 'mp4' in message.mime_type:
        file_path = os.path.abspath('src/forensicWace_SE/'+message.audio_path)
        output_path = file_path.rsplit('.', 1)[0] + '.wav'
        command = [
            'ffmpeg',
            '-y',
            '-i', file_path,
            output_path
        ]
        print(command)

        # Esegui il comando ffmpeg
        try:
            subprocess.run(command, check=True)
            print("Conversione completata!")
        except subprocess.CalledProcessError as e:
            print("Errore durante la conversione:", e)

    if useMsS2T:
        print("Using Microsoft Azure Speech to Text")

        audio_config = speechsdk.AudioConfig(filename=output_path)
        speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

        result = speech_recognizer.recognize_once_async().get()

        message.audio_stt= result.text
        message.text=message.audio_stt

    else:
        print("Using Whisper Speech to Text")

        whisperAI(message, output_path)

    return

def whisperAI(message, output_path):

    files = {
        "audio_file": ("audio", open(output_path, "rb"), "audio/wav")
    }

    headers = {
        "accept": "application/json"
    }

    params = {
        "encode": str(True).lower(),  # true/false in lowercase
        "task": "transcribe",
        "output": "txt"
    }

    response = requests.post(whisperEndpoint, headers=headers, files=files, params=params)

    print(response.status_code)
    print(response.text)

    message.audio_stt= response.text
    message.text=message.audio_stt
    return response.text
