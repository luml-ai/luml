import contextlib
import copy
from typing import Any

from agent.handlers.model_server_handler import ModelServerHandler
from agent.schemas import LocalDeployment


class OpenAPIHandler:
    def __init__(self, model_server_handler: ModelServerHandler) -> None:
        self.ms_handler = model_server_handler

    def _update_schema_refs(
        self,
        schema_obj: Any,  # noqa: ANN401
        deployment_id: str,
        original_schemas: set,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        if isinstance(schema_obj, dict):
            if "$ref" in schema_obj:
                ref_path = schema_obj["$ref"]
                if ref_path.startswith("#/components/schemas/"):
                    ref_name = ref_path.replace("#/components/schemas/", "")
                    if ref_name in original_schemas:
                        schema_obj["$ref"] = (
                            f"#/components/schemas/Deployment{deployment_id}_{ref_name}"
                        )
            else:
                for key, value in schema_obj.items():
                    schema_obj[key] = self._update_schema_refs(
                        value, deployment_id, original_schemas
                    )
        elif isinstance(schema_obj, list):
            for i, item in enumerate(schema_obj):
                schema_obj[i] = self._update_schema_refs(item, deployment_id, original_schemas)
        return schema_obj

    def _process_deployment_schemas(
        self,
        deployment: LocalDeployment,
        openapi_schema: dict[str, Any],  # noqa: ANN401
    ) -> dict[str, str] | None:
        if not deployment.openapi_schema or "components" not in deployment.openapi_schema:
            return None

        model_schema = deployment.openapi_schema
        if "schemas" not in model_schema["components"]:
            return None

        if "schemas" not in openapi_schema["components"]:
            openapi_schema["components"]["schemas"] = {}

        for schema_name, schema_def in model_schema["components"]["schemas"].items():
            self._add_prefixed_schema(
                openapi_schema, deployment.deployment_id, schema_name, schema_def, model_schema
            )

        if "ComputeRequest" in model_schema["components"]["schemas"]:
            result = {
                "deployment_id": deployment.deployment_id,
                "schema_ref": f"#/components/schemas/"
                f"Deployment{deployment.deployment_id}_ComputeRequest",
            }

            if "ComputeResponse" in model_schema["components"]["schemas"]:
                result["response_schema_ref"] = (
                    f"#/components/schemas/Deployment{deployment.deployment_id}_ComputeResponse"
                )

            return result
        return None

    def _add_prefixed_schema(
        self,
        openapi_schema: dict[str, Any],  # noqa: ANN401
        deployment_id: str,
        schema_name: str,
        schema_def: dict[str, Any],  # noqa: ANN401
        model_schema: dict[str, Any],  # noqa: ANN401
    ) -> None:
        prefixed_name = f"Deployment{deployment_id}_{schema_name}"

        updated_schema = self._update_schema_refs(
            copy.deepcopy(schema_def),
            deployment_id,
            set(model_schema["components"]["schemas"].keys()),
        )

        if isinstance(updated_schema, dict):
            updated_schema["title"] = (
                f"[Deployment {deployment_id}] {updated_schema.get('title', schema_name)}"
            )
            if "description" not in updated_schema:
                updated_schema["description"] = f"Schema for deployment {deployment_id}"

        openapi_schema["components"]["schemas"][prefixed_name] = updated_schema

    @staticmethod
    def _update_compute_endpoint(
        openapi_schema: dict[str, Any],
        compute_schemas: list[dict[str, str]],  # noqa: ANN401
    ) -> None:
        compute_path = "/deployments/{deployment_id}/compute"
        if compute_path not in openapi_schema["paths"]:
            return

        if "post" not in openapi_schema["paths"][compute_path]:
            return

        openapi_schema["paths"][compute_path]["post"]["requestBody"] = {
            "content": {
                "application/json": {
                    "schema": {
                        "oneOf": [{"$ref": schema["schema_ref"]} for schema in compute_schemas],
                        "description": (
                            "Compute request schema varies by deployment. "
                            "Use the appropriate schema for your deployment."
                        ),
                    }
                }
            },
            "required": True,
        }

        response_schemas = [s for s in compute_schemas if "response_schema_ref" in s]
        if response_schemas:
            openapi_schema["paths"][compute_path]["post"]["responses"] = {
                "200": {
                    "description": "Successful Response",
                    "content": {
                        "application/json": {
                            "schema": {
                                "oneOf": [
                                    {"$ref": schema["response_schema_ref"]}
                                    for schema in response_schemas
                                ],
                                "description": (
                                    "Compute response schema varies by deployment. "
                                    "The response will match the deployment being called."
                                ),
                            }
                        }
                    },
                }
            }

        deployment_list = ", ".join([str(s["deployment_id"]) for s in compute_schemas])
        description = (
            f"Run inference on a model. Active deployments: {deployment_list}. "
            "The request schema depends on the specific deployment."
        )
        openapi_schema["paths"][compute_path]["post"]["description"] = description

    def merge_deployment_schemas(self, openapi_schema: dict[str, Any]) -> dict[str, Any]:  # noqa: ANN401
        compute_schemas = []

        with contextlib.suppress(Exception):
            for deployment in self.ms_handler.deployments.values():
                compute_schema_info = self._process_deployment_schemas(deployment, openapi_schema)
                if compute_schema_info:
                    compute_schemas.append(compute_schema_info)

        if compute_schemas:
            self._update_compute_endpoint(openapi_schema, compute_schemas)

        return openapi_schema
