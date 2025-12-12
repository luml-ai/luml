from cryptography.fernet import Fernet

from luml.settings import config

fernet = Fernet(config.BUCKET_SECRET_KEY)


def encrypt(value: str) -> str:
    return fernet.encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return fernet.decrypt(value.encode()).decode()
