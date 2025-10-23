import re
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
import base64
from itertools import cycle
import logging
logger = logging.getLogger(__name__)

SWAPIX_PUB_KEY = """\
-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAkfLufn8NcFq07NVHltwU
DI8odIpNs+rbqNzIVFfrKM20PpV+rmHroJDA1YSobI/hOFqjqnS1gMcsAC5fCJ1r
bf4uB4udp9UiNLvP9tKTzZzLdK5g4y5HKSMSZ0vA53S1cklNqCv2ACVsFdSj2vC4
SD7L7kkrUwo73JJT98ZW6hOrjQXeIxq8qHpxo9eON5EG4T5RzVywT8d5ZeQ1kNn5
1mAFRu0lho88CBc2mf+nmY/HblSU3TrqubVW2kXjLZunx+FeJtWmU5IlXakQA4VA
/cD2wFu4lEDrMqdQtT0jwjcy1Rp1WTVzfX2e37Vzta5xNnYTpm0D/M4vhenFFxKK
s8k8Tzix5sS2tH/DRYJqcxP4/Nm87q8sdzHSWLrOcfKcj/bdtp0qwSmXH4MMNFHj
AERl9W0NLs3j77FBLuNwxeGA+ACyoOxRrOhHtZkgozhkYNfV8sCoY2w/MA79zrsl
US/Et+VDgzAmbkxAVb/Fyhf1/C70T8b0P+OgO99mCk1bN8s9cNtGOkUanUTfikzq
6wRDMKnC7Edm9OerenLy4pzfd35hEJHWkpWNkp142X+Ai60PBZ/UYBe3rbsDhhT4
1zPhiFv6IPRvgaxa8UmTkAwpHlfbnH3ujm2xo2VxYpOI+CupIOUSwbByUKVNoEzA
VStH5JpB1SAgNma4wcYEg00CAwEAAQ==
-----END PUBLIC KEY-----"""

def calculate_checksum(data):
    crc = 0xFFFF
    polynomial = 0x1021
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if (crc & 0x8000):
                crc = (crc << 1) ^ polynomial
            else:
                crc = crc << 1
            crc &= 0xFFFF
    return crc

def validate_checksum(data) -> bool:
    # Extract the checksum from the last four digits of the string
    extracted_checksum = int(data[-4:], 16)

    # Remove the last four digits to get the message content
    message_content = data[:-4]

    # Calculate the checksum for the message content
    calculated_checksum = calculate_checksum(message_content.encode())

    # Validate the checksum
    return (extracted_checksum == calculated_checksum)


def detect_qr_pix_type(qr_code: str) -> str:
    """
    Detect if a QR PIX is static or dynamic based on the initial fields.
    Args:
        qr_code: The complete QR PIX code
    Returns:
        'STATIC' if it is a static QR, 'DYNAMIC' if it is a dynamic QR, 'UNKNOWN' if it cannot be determined
    """
    try:
        # Pattern 1: 00020101021X where X determines the type
        if qr_code.startswith('0002010102'):
            type_indicator = qr_code[10:12]
            if type_indicator == '11':
                return 'STATIC'
            elif type_indicator == '12':
                return 'DYNAMIC'
        # Pattern 2: 00020126 indicates static
        elif qr_code.startswith('00020126'):
            return 'STATIC'

        return 'UNKNOWN'

    except Exception as e:
        logger.error(msg=f"detect_qr_pix_type error", extra= {"QRPayload": qr_code, "error": str(e)})
        return 'UNKNOWN'


def formatPixKey(pixkey):
    # qrcode
    if len(pixkey) > 36:
        try:
            if not validate_checksum(pixkey):
                logger.warning(msg=f"checksum error", extra= {"QRPayload": pixkey})
                return [False, "QR checksum Error", 'QRCODE']
            else:
                qr_type = detect_qr_pix_type(pixkey)
                if qr_type == 'STATIC':
                    return [True, pixkey, 'QRCODE_STATIC']
                elif qr_type == 'DYNAMIC':
                    return [True, pixkey, 'QRCODE_DYNAMIC']
                else:
                    return [True, pixkey, 'QRCODE']
        except:
            pass

    # email
    if "@" in pixkey:
        if not isMail(pixkey):
            logger.debug(msg=f'isMail: Invalid Email {pixkey}')
            return [False, "Invalid Email", 'EMAIL']
        return [True, pixkey.lower(), 'EMAIL']

    # phone
    if "+" in pixkey:
        pixkey = "+" + re.sub(r'[^\d]+', '', pixkey)
        if len(pixkey) != 14:
            return [False, "Invalid Phone number", 'PHONE']
        if pixkey[:3] != "+55":
            return [False, "Not Brazilian number", 'PHONE']
        return [True, pixkey, 'PHONE']

    # key
    if len(pixkey) == 36:
        return [True, pixkey, 'EVP']

    # formatted cnpj
    if len(pixkey) == 18:
        if not re.match(r'^\d{2}\.\d{3}\.\d{3}\/\d{4}\-\d{2}$', pixkey):
            return [False, "Invalid pixkey", 'UNKNOWN']
        if not isCnpj(pixkey):
            return [False, "Invalid cnpj", 'CNPJ']
        pixkey = re.sub(r'[^\d]+', '', pixkey)
        return [True, pixkey, 'CNPJ']

    # fone with missing +
    if len(pixkey) == 13:
        if re.match(r'^\d+$', pixkey):
            if pixkey[:2] != "55":
                return [False, "Invalid pixkey", 'UNKNOWN']
            return [True, "+" + pixkey, 'PHONE']

    # every other option has at least 11 chars
    if len(pixkey) < 11:
        return [False, "Invalid pixkey", 'UNKNOWN']

    # cnpj or formatted cpf
    if len(pixkey) == 14:
        # unformatted cnpj
        if re.match(r'^\d+$', pixkey):
            if not isCnpj(pixkey):
                return [False, "Invalid pixkey", 'UNKNOWN']
            return [True, pixkey, 'CNPJ']
        # formatted cpf
        if re.match(r'^\d{3}\.\d{3}\.\d{3}\-\d{2}$', pixkey):
            if not isCpf(pixkey):
                return [False, "Invalid cpf", 'CPF']
            return [True, re.sub(r'[^\d]+', '', pixkey), 'CPF']

    # formatted cpf or phone without country
    if len(pixkey) == 11:
        if not re.match(r'^\d+$', pixkey):
            return [False, "Invalid pixkey", 'UNKNOWN']
        if isCpf(pixkey):
            return [True, re.sub(r'[^\d]+', '', pixkey), 'CPF']
        if pixkey[0] == "0":
            return [False, "Invalid pixkey", 'UNKNOWN']
        return [True, "+55" + pixkey, 'PHONE']

    # either wrong formatted cpf or formatted phone number
    pixkey = re.sub(r'[^\d]+', '', pixkey)
    if len(pixkey) == 12:
        if pixkey[0] != "0":
            return [False, "Either wrong formatted cpf or formatted phone number", 'UNKOWN']
        return [True, "+55" + pixkey[1:], 'PHONE']

    if len(pixkey) == 11:
        if isCpf(pixkey):
            return [True, pixkey, 'CPF']
        return [True, "+55" + pixkey, 'PHONE']

    return [False, "Invalid pixkey", 'UNKNOWN']

def isMail(email):
    re_pattern = r'^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$'
    return bool(re.match(re_pattern, email.lower()))


def _only_numbers(s: str) -> str:
    return re.sub(r"[^\d]+", "", s)


def isCpf(cpf):
    cpf = re.sub(r"[^\d]+", "", cpf)
    if cpf == "":
        return False
    if len(cpf) != 11 or cpf in [
        "00000000000",
        "11111111111",
        "22222222222",
        "33333333333",
        "44444444444",
        "55555555555",
        "66666666666",
        "77777777777",
        "88888888888",
        "99999999999",
    ]:
        return False
    Soma = 0
    for i in range(1, 10):
        Soma = Soma + int(cpf[i - 1]) * (11 - i)
    Resto = (Soma * 10) % 11
    if Resto == 10 or Resto == 11:
        Resto = 0
    if Resto != int(cpf[9]):
        return False

    Soma = 0
    for i in range(1, 11):
        Soma = Soma + int(cpf[i - 1]) * (12 - i)
    Resto = (Soma * 10) % 11
    if Resto == 10 or Resto == 11:
        Resto = 0
    if Resto != int(cpf[10]):
        return False
    return True


def isCnpj(cnpj):
    cnpj = _only_numbers(cnpj)

    if len(cnpj) != 14 or len(set(cnpj)) == 1:
        return False

    def calculate_digit(number: str) -> str:
        weights = cycle(range(2, 10))
        acc = sum(int(num) * weight for (num, weight) in zip(reversed(number), weights))
        result = 11 - (acc % 11)
        return "0" if result >= 10 else str(result)

    digit1 = calculate_digit(cnpj[:12])
    digit2 = calculate_digit(cnpj[:13])

    return cnpj[-2:] == digit1 + digit2


def memo_encrypt(memo):
    swapix_pub_key = serialization.load_pem_public_key(SWAPIX_PUB_KEY.encode())

    # Message to be encrypted
    message = memo

    # Convert the message to bytes
    message_bytes = message.encode()

    # Encrypt the message using RSA with OAEP SHA-256 padding
    encrypted = swapix_pub_key.encrypt(
        message_bytes,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

    # Convert the encrypted bytes to base64 encoded string
    encrypted_base64 = base64.b64encode(encrypted).decode()
    return(encrypted_base64)
