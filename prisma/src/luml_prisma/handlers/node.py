from typing import Any

from luml_prisma.infra.exceptions import (
    InvalidOperationError,
    NodeNotFoundError,
)
from luml_prisma.repositories.node import RunNodeRepository
from luml_prisma.services.orchestrator.engine import OrchestratorEngine
from luml_prisma.services.pty_manager import PtyManager


class NodeHandler:
    def __init__(
        self,
        node_repo: RunNodeRepository,
        pty: PtyManager,
        engine: OrchestratorEngine,
    ) -> None:
        self._nodes = node_repo
        self._pty = pty
        self._engine = engine

    def send_input(
        self, node_id: str, text: str,
    ) -> None:
        node = self._nodes.get_node(node_id)
        if not node:
            raise NodeNotFoundError
        sessions = self._nodes.get_sessions(node_id)
        for s in sessions:
            if self._pty.is_alive(s.session_id):
                self._pty.write(
                    s.session_id, text.encode(),
                )
                return
        raise InvalidOperationError(
            "No active session for node"
        )

    async def execute_action(
        self,
        node_id: str,
        action: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        node = self._nodes.get_node(node_id)
        if not node:
            raise NodeNotFoundError

        if action == "cancel":
            await self._engine.cancel_node(
                node.run_id, node_id,
            )
            return {"status": "canceled"}

        if action == "approve_fork":
            proposals = payload.get("proposals", [])
            for p in proposals:
                self._engine._spawn_child(
                    node.run_id,
                    node,
                    "implement",
                    {"prompt": p.get("prompt", "")},
                    "fork",
                )
            return {
                "status": "approved",
                "children": len(proposals),
            }

        raise InvalidOperationError(
            f"Unknown action: {action}"
        )
