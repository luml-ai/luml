from luml_agent.services.orchestrator.nodes.base import NodeHandler


class NodeRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, NodeHandler] = {}

    def register(self, handler: NodeHandler) -> None:
        self._handlers[handler.type_id()] = handler

    def get(self, type_id: str) -> NodeHandler | None:
        return self._handlers.get(type_id)

    def list_types(self) -> list[str]:
        return list(self._handlers.keys())


_registry = NodeRegistry()


def get_registry() -> NodeRegistry:
    return _registry


def register_all_handlers() -> NodeRegistry:
    from luml_agent.services.orchestrator.nodes.debug import DebugNodeHandler
    from luml_agent.services.orchestrator.nodes.fork import ForkNodeHandler
    from luml_agent.services.orchestrator.nodes.implement import ImplementNodeHandler
    from luml_agent.services.orchestrator.nodes.run_node import RunNodeHandler

    registry = get_registry()
    registry.register(ImplementNodeHandler())
    registry.register(RunNodeHandler())
    registry.register(DebugNodeHandler())
    registry.register(ForkNodeHandler())
    return registry
