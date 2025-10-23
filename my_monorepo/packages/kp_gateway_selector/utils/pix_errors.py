class PixProviderException(Exception):
    """Base class for all Pix-related exceptions."""
    def __init__(self, message: str, status_code: int = 500, pix_key: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.pix_key = pix_key


class PixHttpClientFailure(PixProviderException):
    def __init__(self, message: str, status_code: int = 400,pix_key: str = None):
        super().__init__(message, status_code,pix_key)


class PixServerError(PixProviderException):
    def __init__(self, message: str="An unexpected error occurred.", status_code: int = 500,pix_key: str = None):
        super().__init__(message, status_code,pix_key)


class PixValidationAuthFailure(PixProviderException):
    def __init__(self, message: str = "Authentication failed or Invalid API User", pix_key: str = None):
        super().__init__(message, 401,pix_key)


class PixValidationBadPayload(PixProviderException):
    def __init__(self, message: str = "Invalid Payload", pix_key: str = None):
        super().__init__(message, 400,pix_key)


class PixGenericError(PixProviderException):
    def __init__(self, message: str = "A service error occurred", pix_key: str = None):
        super().__init__(message, 500,pix_key)


class PixUpstreamError(PixProviderException):
    def __init__(self, message: str = "Internal supplier error", pix_key: str = None):
        super().__init__(message, 500,pix_key)

class PixValidationInvalidFormat(PixProviderException):
    def __init__(self, reformatted_key: str):
        self.reformatted_key = reformatted_key
        super().__init__("invalid format", status_code=400)
class PixConnectionError(PixProviderException):
    def __init__(self, message: str = "Unable to connect to the provider", pix_key: str = None):
        super().__init__(message, 500,pix_key)

class PixKeyQRExpire(PixProviderException):
    def __init__(self, message: str = "QR expire", pix_key: str = None):
        super().__init__(message, 500,pix_key)


TYPE_ERROR_PIX_KEY = {
    "QRCODE": "Expired or Invalid QR code",
    "QRCODE_STATIC": "Expired or Invalid QR code",
    "QRCODE_DYNAMIC": "Expired or Invalid QR code",
    "DEFAULT": "pix key not found",
}