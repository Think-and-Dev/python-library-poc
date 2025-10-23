from enum import Enum
from typing import Optional

class GatewaysEnum(int, Enum):
    e2e_processor = 1
    swapix_prepaid = 2

class SwapixCurrency(Enum):
    polygon = 'pxusdt'
    tron = 'txusdt'

class CurrencyPairEnum(str, Enum):
    BRLUSDT = "BRLUSDT"
    USDTBRL = "USDTBRL"
    ARSBRL = "ARSBRL"
    BRLARS = "BRLARS"

class FixedPairEnum(str, Enum):
    ARSBRL = "ARSBRL"

class FrontPairEnum(str, Enum):
    ARSBRL = "ARSBRL"
    BRLUSDT = "BRLUSDT"
    USDTBRL = "USDTBRL"

class ServiceTypeEnum(str, Enum):
    PAY = "pay"
    CHARGE = "charge"

class ChainEnum(str, Enum):
    POLYGON = "polygon"
    TRON = "tron"

    @staticmethod
    def get_token(chain: Optional['ChainEnum']) -> str:
        if chain is None or chain == ChainEnum.POLYGON:
            return 'pxusdt'
        elif chain == ChainEnum.TRON:
            return 'txusdt'

class TokenEnum(str, Enum):
    PXUSDT = 'pxusdt'
    TXUSDT = 'txusdt'

class ExchangeEnum(str, Enum):
    FIWIND = 'fiwind'
    LEMON = 'lemoncash'
    BELO = 'belo'
    BUENBIT = 'buenbit'
    BINANCE = 'binance'

class CurrencyLayoutEnum(Enum):
    ARS = 1
    USDT = 3
    BRL = 4

class OracleActions(Enum):
    ARS = (1, 2)
    USDT = (4, 2)
    BRL = (1, 5)

class RpcProviderEnum(str, Enum):
    QUICKNODE = "QUICKNODE"
    TATUM = "TATUM"
    ALCHEMY = "ALCHEMY"

class PaymentGateway(Enum):
    E2E = 1
    PREPAID_SWAPIX = 2
    CELCOIN = 3


# Define the operation_types enum
class OperationTypes(Enum):
    REFILL = "REFILL"
    FEE = "FEE"
    TOPUP = "TOPUP"
    # Add other operation types as needed


class BlockchainStatuses(Enum):
    CREATED = 'CREATED'
    PROCESSING = 'PROCESSING'
    MINED = 'MINED'
    ERROR = 'ERROR'


class PixKeyType(Enum):
    EMV_STATIC = 1
    EMV_DYNAMIC = 2
    PIXKEY = 3

    @classmethod
    def from_string(cls, value: str) -> 'PixKeyType':
        return cls[value.upper()]# Implementation here


class DictKeyType(Enum):
    EMAIL = 1
    CPF = 2
    CNPJ = 3
    EVP = 4
    EMV = 5
    PHONE = 6
    @classmethod
    def from_string(cls, value: str) -> 'DictKeyType':
        value_map = {
            'EMAIL': cls.EMAIL,
            'CPF': cls.CPF,
            'CNPJ': cls.CNPJ,
            'EVP': cls.EVP,
            'EMV': cls.EMV,
            'PHONE': cls.PHONE
        }
        return value_map.get(value.upper(), cls.EMAIL)



# tx status
class PrePaidV1StatusMapping(Enum):
    CREATED = 1
    CANCELED = 2
    FAILED = 7
    PROCESSING = 8
    CONFIRMING = 9
    DONE = 10
    PREFUNDED = 11
    REFUNDED = 12
    UNKNOWN = 99

    @classmethod
    def from_string(cls, value: str) -> 'PrePaidV1StatusMapping':
        try:
            # Convert input to uppercase and match against Enum names
            return cls[value.upper()]
        except KeyError:
            ### LOGUEAR  (f"Invalid status string: {value}. Expected one of {[e.name.lower() for e in cls]}")
            return cls.UNKNOWN

    @property
    def text(self) -> str:
        """Returns the lowercase name of the status"""
        return self.name.lower()

    @classmethod
    def from_id(cls, status_id: int) -> 'PrePaidV1StatusMapping':
        """Convert numeric ID to Enum member"""
        for member in cls:
            if member.value == status_id:
                return member
        return cls.UNKNOWN
    @classmethod
    def from_id_e2e_pay_out_without_refunds(cls, status_id: int) -> 'PrePaidV1StatusMapping':
        """it only responds Done for payouts without updating refunded/refund status
        status 11 and 12 are adjusted to 10"""
        if status_id in [11, 12]:
            status_id = 10
        for member in cls:
            if member.value == status_id:
                return member
        return cls.UNKNOWN
    @classmethod
    def is_new_processing_or_done(cls, status_id: int) -> bool:
        """Returns True if status_id is NEW, PROCESSING, or DONE, False otherwise"""
        return status_id in (cls.CREATED.value, cls.PROCESSING.value, cls.DONE.value)
    @classmethod
    def is_processing_or_done(cls, status_id: int) -> bool:
        """Returns True if status_id is NEW, PROCESSING, or DONE, False otherwise"""
        return status_id in (cls.PROCESSING.value, cls.DONE.value)