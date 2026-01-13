import httpx
import requests
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential
import os

from src.forensicWace_SE import utils

configIniFile = utils.ReadConfigFile()

# Set the values of your computer vision endpoint and computer vision key
# as environment variables:
endpoint = configIniFile['API']['mscvendpoint']
key = configIniFile['API']['mscvkey']
language = configIniFile['API']['mscvlanguage']
tesseractEndpoint = configIniFile['API']['ocrtesseractendpoint']
lavisEndpoint = configIniFile['API']['imagecaptionlavisendpoint']

useMsCaptionAndOcr = True if configIniFile['Pay2UseAnalyzers']['msazureocrandcaption'] == 'on' else False

client = ImageAnalysisClient(
    endpoint=endpoint,
    credential=AzureKeyCredential(key)
)

def check_status_Microsoft():

    if useMsCaptionAndOcr:
        if isinstance(key, str):
            print("Valid MS_CV_key key")
            if isinstance(language, str):
                print("Valid MS_CV language")
                if isinstance(endpoint, str):
                    print("Valid MS_CV endpoint")
                    try:
                        basePath = os.path.dirname(os.path.abspath(__file__))
                        testImagePathCaption = basePath + "/AnalyzerAvailabilityCheckResources/ImageCaptionAnalyzerTest.PNG"

                        with open(os.path.abspath(testImagePathCaption), "rb") as imageFile:
                            image_data = imageFile.read()

                        visual_features = [
                            # VisualFeatures.TAGS,
                            # VisualFeatures.OBJECTS,
                            VisualFeatures.CAPTION,
                            # VisualFeatures.DENSE_CAPTIONS,
                            # VisualFeatures.READ,
                            # VisualFeatures.SMART_CROPS,
                            # VisualFeatures.PEOPLE,
                        ]

                        # Get a caption for the image. This will be a synchronously (blocking) call.
                        result = client.analyze(
                            image_data=image_data,
                            visual_features=visual_features,
                            # gender_neutral_caption=True,
                            language=language
                        )
                        if result.caption is not None:
                            print(f"   '{result.caption.text}', Confidence {result.caption.confidence:.4f}")
                            if "cat" in result.caption.text:
                                return True, "MS_CV", "MS_CV is working"
                        else:
                            return False, "MS_CV", "MS_CV Caption not working"
                    except Exception as e:
                        print(e)
                        return False, "MS_CV", e
                else:
                    print("Invalid MS_CV endpoint")
                    return False, "MS_CV", "Invalid MS_CV endpoint"
            else:
                print("Invalid MS_CV language")
                return False, "MS_CV", "Invalid MS_CV language"
        else:
            print("Unvalid Azure key")
            return False, "MS_CV", "Invalid Azure key"
    else:
        return False, "MS_CV", "Microsoft Service not selected"



def check_status_TesseractOCR():
    payload = {'options': '{"languages":["eng"]}'}
    if tesseractEndpoint:
        try:
            basePath = os.path.dirname(os.path.abspath(__file__))
            testImagePathOCR = basePath + "/AnalyzerAvailabilityCheckResources/ImageOcrAnalyzerTest.png"

            with open(os.path.abspath(testImagePathOCR), "rb") as imageFile:
                files = [
                    ('file', ("ImageOcrAnalyzerTest.png",
                              imageFile,
                              'image/jpeg'))
                ]
                headers = {}

                response = requests.request("POST", tesseractEndpoint, headers=headers, data=payload, files=files)

                text = response.json()["data"]["stdout"]

                if "FORENSIC WACE" in text.strip():
                    return True, "Tesseract", "Tesseract OCR is working"
                else:
                    return False, "Tesseract", "Tesseract OCR is not working properly: " + text
        except Exception as e:
            print(e)
            return False, "Tesseract", e

    else:
        return False, "Tesseract", "Tesseract OCR endpoint is void"


def check_status_LavisCaption():
    payload = {}
    if lavisEndpoint:
        try:
            basePath = os.path.dirname(os.path.abspath(__file__))
            testImagePathCaption = basePath + "/AnalyzerAvailabilityCheckResources/ImageCaptionAnalyzerTest.PNG"

            with open(os.path.abspath(testImagePathCaption), "rb") as imageFile:
                files = [
                    ('file', ("ImageCaptionAnalyzerTest.PNG",
                              imageFile,
                              'image/jpeg'))
                ]
                headers = {}

                response = requests.request("POST", lavisEndpoint, headers=headers, data=payload, files=files)
                caption = response.json()["caption"]

                if "cat" or "kitten" or "bucket" in caption:
                    return True, "Lavis", "Lavis Caption is working"
                else:
                    return False, "Lavis", "Lavis Caption is not working properly: "+caption
        except Exception as e:
            print(e)
            return False, "Lavis", e

    else:
        return False, "Lavis", "Lavis Caption endpoint is void"


def imageDesc(message):
    res = {}

    if useMsCaptionAndOcr:
        print("Using Microsoft Azure Computer Vision for image caption and OCR")

        # Load image to analyze into a 'bytes' object
        with open(os.path.abspath('src/forensicWace_SE/' + message.image_path), "rb") as imageFile:
            image_data = imageFile.read()

        visual_features = [
            #VisualFeatures.TAGS,
            #VisualFeatures.OBJECTS,
            VisualFeatures.CAPTION,
            #VisualFeatures.DENSE_CAPTIONS,
            VisualFeatures.READ,
            #VisualFeatures.SMART_CROPS,
            #VisualFeatures.PEOPLE,
        ]

        # Get a caption for the image. This will be a synchronously (blocking) call.
        result = client.analyze(
            image_data=image_data,
            visual_features=visual_features,
            #gender_neutral_caption=True,
            language=language
        )
        print("Image analysis results:")
        # Print caption results to the console
        print(" Caption:")
        if result.caption is not None:
            print(f"   '{result.caption.text}', Confidence {result.caption.confidence:.4f}")
            res['caption'] = result.caption.text
            message.image_caption = res['caption']
            message.text = (message.text or "") + " "+ message.image_caption
        # Print text (OCR) analysis results to the console
        print(" Read:")
        if len(result.read.blocks) > 0:
            all_words = []  # List to accumulate all the words
            for line in result.read.blocks[0].lines:
                print(f"   Line: '{line.text}', Bounding box {line.bounding_polygon}")
                for word in line.words:
                    print(
                        f"     Word: '{word.text}', Bounding polygon {word.bounding_polygon}, Confidence {word.confidence:.4f}")
                    all_words.append(word.text)  # Add each word to the list

            concatenated_words = ' '.join(all_words)  # Join all words with a space
            res['OCR'] = concatenated_words
            message.image_OCR = res['OCR']
            message.text = (message.text or "") + " " + message.image_OCR

    else:
        print("Using Tesseract and Lavis for image caption and OCR")

        tesseractOCR(message)
        lavisCaption(message)

    return res

def tesseractOCR(message):
    payload = {'options': '{"languages":["eng"]}'}

    # Load image to analyze into a 'bytes' object
    with open(os.path.abspath('src/forensicWace_SE/' + message.image_path), "rb") as imageFile:
        print("Image file successfully opened for OCR")

        files = [
            ('file', (message.image_path,
                      imageFile,
                      'image/jpeg'))
        ]
        headers = {}

        response = requests.request("POST", tesseractEndpoint, headers=headers, data=payload, files=files)

        text= response.json()["data"]["stdout"]
        res = {}
        res['OCR'] = text
        message.image_OCR = res['OCR']
        message.text = (message.text or "") + " " + message.image_OCR

    return res

def lavisCaption(message):
    payload = {}

    # Load image to analyze into a 'bytes' object
    with open(os.path.abspath('src/forensicWace_SE/' + message.image_path), "rb") as imageFile:
        print("Image file successfully opened for captioning")

        files = [
            ('file', (message.image_path,
                      imageFile,
                      'image/jpeg'))
        ]

        headers = {}

        response = requests.request("POST", lavisEndpoint, headers=headers, data=payload, files=files)
        caption = response.json()["caption"]

        res = {}
        res['caption'] = caption
        message.image_caption = res['caption']
        message.text = (message.text or "") + " " + message.image_caption

    return res