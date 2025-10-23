from typing import Generic, Optional, TypeVar, Dict, Type, Callable
from utils.constants import TTLUnit
import json
import redis
from sqlalchemy.orm import Session
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0
DEFAULT_TTL = 300
PIX_KEY_FAIL_TTL = 60
PIX_KEY_SUCCESS_TTL = 300
from dataclasses import is_dataclass
from dataclasses import asdict
import logging
logger = logging.getLogger(__name__)
T = TypeVar("T")


class RedisBaseCache(Generic[T]):
    """
    Base genérica para cachés Redis, con soporte para serialización de dataclasses,
    uso de deserializadores personalizados, y configuración de TTL dinámica por tipo de dato.

    """

    _cache_client = None

    def __init__(self, cls_type: Optional[Type[T]] = None, deserializer: Optional[Callable[[dict], T]] = None):
        """
        Inicializa el cliente Redis y configura tipo de datos y deserializador.

        Args:
            cls_type (Optional[Type[T]]): Clase del tipo esperado a recuperar desde Redis.
            deserializer (Optional[Callable[[dict], T]]): Función opcional para deserializar manualmente.
        """
        if RedisBaseCache._cache_client is None:
            RedisBaseCache._cache_client = redis.StrictRedis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB
            )

        self._client = RedisBaseCache._cache_client
        self.db: Optional[Session] = None
        self._prefix = f"{self.__class__.__name__}".lower()
        self.cls_type = cls_type
        self.deserializer = deserializer

    def set_db(self, db: Session):
        """
        Asigna la instancia de base de datos para obtener valores de TTL dinámicos.

        Args:
            db (Session): Sesión activa de SQLAlchemy.
        """
        self.db = db

    def build_cache_key(self, key: str) -> str:
        """
        Construye la clave completa para Redis, usando el nombre de la clase como prefijo.
        Convierte la clave a minúsculas y reemplaza espacios con guiones bajos para mantener consistencia.

        Args:
            key (str): Identificador de la clave.

        Returns:
            str: Clave formateada con prefijo en minúsculas y espacios normalizados.
        """
        # Convert to lowercase and replace spaces with underscores
        normalized_key = key.lower().strip().replace(' ', '_')
        return f"{self._prefix}:{normalized_key}"

    def set(self, key: str, value: T, ttl: int, ttl_unit: TTLUnit = TTLUnit.SECONDS) -> None:
        """
        Guarda un valor en Redis con TTL. Si falla, se loguea el error sin interrumpir el flujo.

        Args:
            key (str): Clave de la caché.
            value (T): Valor a almacenar.
            ttl (int): Tiempo de expiración en segundos/milisegundos(depende de la unidad de tiempo)
            ttl_unit(TTLUnit): Unidad de tiempo del ttl, por default en segundos.
        """
        try:
            if is_dataclass(value):
                data = asdict(value)
            else:
                data = value

            self._client.set(self.build_cache_key(key), json.dumps(data),**{ttl_unit.value: ttl})#unpacking: convierte {'ex': ttl} en ex=ttl (o 'px': ttl en px=ttl)
        except Exception as e:
            logger.error(f"[RedisBaseCache] Error setting key '{self.build_cache_key(key)}': {e}")

    def getdel(self, key: str) -> Optional[T]:
        """
        Recupera un valor desde Redis y de ser exitoso, lo elimina (si y solo si el valor de la key es del tipo string).
        Si ocurre una excepción, devuelve None y loguea el error.

        Args:
            key (str): Clave de la caché.

        Returns:
            Optional[T]: Objeto recuperado o None si no existe o falla.
        """
        try:
            raw = self._client.getdel(self.build_cache_key(key))
            if not raw:
                return None
            data = json.loads(raw.decode("utf-8"))

            if self.deserializer:
                return self.deserializer(data)

            if self.cls_type and is_dataclass(self.cls_type):
                return self.cls_type(**data)

            return data  # dict, str, list, etc.

        except Exception as e:
            logger.error(f"[RedisBaseCache] Error getting key '{self.build_cache_key(key)}': {e}")
            return None

    def get(self, key: str) -> Optional[T]:
        """
        Recupera un valor desde Redis. Si ocurre una excepción, devuelve None y loguea el error.

        Args:
            key (str): Clave de la caché.

        Returns:
            Optional[T]: Objeto recuperado o None si no existe o falla.
        """
        try:
            raw = self._client.get(self.build_cache_key(key))
            if not raw:
                return None
            data = json.loads(raw.decode("utf-8"))

            if self.deserializer:
                return self.deserializer(data)

            if self.cls_type and is_dataclass(self.cls_type):
                return self.cls_type(**data)

            return data  # dict, str, list, etc.

        except Exception as e:
            logger.error(f"[RedisBaseCache] Error getting key '{self.build_cache_key(key)}': {e}")
            return None

    def delete(self, key: str):
        """
        Elimina una clave de Redis. Si ocurre un error, se loguea y continúa.

        Args:
            key (str): Clave a eliminar.
        """
        try:
            self._client.delete(self.build_cache_key(key))
        except Exception as e:
            logger.error(f"[RedisBaseCache] Error deleting key '{self.build_cache_key(key)}': {e}")

    def get_ttl(self, suffix: Optional[str] = None, default: Optional[int] = None) -> int:
        """
        Obtiene el TTL configurado. En la versión de librería, esto solo devuelve el valor por defecto.
        """
        fallback = default or DEFAULT_TTL
        return fallback

    def get_success_ttl(self) -> int:
        """
        Devuelve el TTL para operaciones exitosas.

        Returns:
            int: TTL configurado o valor por defecto.
        """
        return self.get_ttl("SUCCESS_TTL", PIX_KEY_SUCCESS_TTL)

    def get_fail_ttl(self) -> int:
        """
        Devuelve el TTL para operaciones fallidas.

        Returns:
            int: TTL configurado o valor por defecto.
        """
        return self.get_ttl("FAIL_TTL", PIX_KEY_FAIL_TTL)

    def get_ttl_options(self) -> Dict[int, int]:
        """
        Devuelve un diccionario con los TTL por código de estado (e.g. 200, 400).

        Returns:
            Dict[int, int]: Mapeo de códigos a TTLs.
        """
        return {
            200: self.get_success_ttl(),
            400: self.get_fail_ttl(),
        }