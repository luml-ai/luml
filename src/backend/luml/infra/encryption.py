from functools import lru_cache

from cryptography.fernet import Fernet


@lru_cache
def _get_fernet() -> Fernet:
    from luml.settings import config

    return Fernet(config.BUCKET_SECRET_KEY)


def encrypt(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _get_fernet().decrypt(value.encode()).decode()
