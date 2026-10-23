from uuid import uuid4


class Store:
    _store = {}

    @classmethod
    def save(cls, value) -> str:
        key = str(uuid4())
        cls._store[key] = value
        return key

    @classmethod
    def get(cls, key):
        return cls._store[key]

    @classmethod
    def pop(cls, key):
        return cls._store.pop(key, None)

    @classmethod
    def delete(cls, key):
        cls.pop(key)
