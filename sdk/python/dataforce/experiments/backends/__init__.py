from dataforce.experiments.backends._base import Backend
from dataforce.experiments.backends.sqlite import SQLiteBackend


class BackendRegistry:
    backends: dict = {}

    @classmethod
    def register(cls, backend_type: str, backend_class: type) -> None:
        if backend_type in cls.backends:
            raise ValueError(f"Backend type '{backend_type}' is already registered.")
        cls.backends[backend_type] = backend_class

    @classmethod
    def get_backend(cls, backend_type: str) -> type[Backend]:
        if backend_type not in cls.backends:
            raise ValueError(f"Backend type '{backend_type}' is not registered.")
        return cls.backends[backend_type]


BackendRegistry.register("sqlite", SQLiteBackend)
