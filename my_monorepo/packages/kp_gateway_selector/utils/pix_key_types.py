from enum import Enum


class PixKeyTypes(Enum):
    QRCODE = "QRCODE"
    QRCODE_STATIC = "QRCODE_STATIC"
    QRCODE_DYNAMIC = "QRCODE_DYNAMIC"
    EMAIL = "EMAIL"
    PHONE = "PHONE"  # -
    EVP = "EVP"  # Enderezo Virtual de Pagamento [Llave Aleatoria]
    CPF = "CPF"
    CNPJ = "CNPJ"
