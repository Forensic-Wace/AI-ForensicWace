import os

import httpx
from dotenv import load_dotenv
import re
from src.forensicWace_SE import utils
from src.forensicWace_SE.repository.models import Text, Password
import json

configIniFile = utils.ReadConfigFile()

baseurl = configIniFile['API']['deeppassendpoint']

def check_status():
    if isinstance(baseurl, str):
        # Espressione regolare per validare un URL
        pattern = re.compile(
            r'https?://'  # http:// o https://
            r'(localhost|'  # localhost
            r'(\d{1,3}\.){3}\d{1,3}|'  # IP address (es. 127.0.0.1)
            r'([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,})'  # dominio (es. example.com)
            r'(:\d+)?'  # porta opzionale (es. :5000)
            r'(/[^\s]*)?'  # path opzionale
        )

        if bool(pattern.match(baseurl)):
            try:
                res = httpx.post(baseurl + "/api/text", data="paswetr%")
                json_response = json.loads(res.text)

                psw_detected = json_response['model_password_candidates'][0]['password'] == 'paswetr%'

                if psw_detected:
                    return True, "DeepPass", "DeepPass is working"
                else:
                    return False, "DeepPass", "DeepPass is not working"
            except Exception as e:
                print(e)
                return False, "DeepPass", e
        else:
            return False, "DeepPass", "Check method NOT implemented"
    else:
        return False, "DeepPass", "Check method NOT implemented"



def populate_get_deep_passwords(text: Text):
    res = httpx.post(baseurl + "/api/text", data=text.text)
    res = res.json()
    model_passwords = [a['password'] for a in res['model_password_candidates']]
    regex_passwords = [a['password'] for a in res['regex_password_candidates']]

    if model_passwords:
        for psw_text in model_passwords:
            psw = Password(password=psw_text, source='deeppass_model')
            text.password.append(psw)
    if regex_passwords:
        for psw_text in regex_passwords:
            if psw_text not in model_passwords:
                psw = Password(password=psw_text, source='deeppass_regex')
                text.password.append(psw)

    return model_passwords, regex_passwords


def get_deep_passwords(text):
    res = httpx.post(baseurl + "/api/text", data=text)
    res = res.json()
    model_passwords = [a['password'] for a in res['model_password_candidates']]
    regex_passwords = [a['password'] for a in res['regex_password_candidates']]

    psw_array = []
    if model_passwords:
        for psw_text in model_passwords:
            psw_array.append(psw_text)
    if regex_passwords:
        for psw_text in regex_passwords:
            if psw_text not in model_passwords:
                psw_array.append(psw_text)

    return psw_array
