from agent.handlers.model_server_handler import ModelServerHandler
from agent.handlers.secrets_handler import SecretsHandler

ms_handler = ModelServerHandler()
secrets_handler = SecretsHandler()


__all__ = ["ms_handler", "secrets_handler"]
