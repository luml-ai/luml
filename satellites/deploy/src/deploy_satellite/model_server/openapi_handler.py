"""OpenAPI schema handler for merging deployment schemas."""

from __future__ import annotations

import contextlib
import copy
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from deploy_satellite.model_server.handler import ModelServerHandler
    from deploy_satellite.model_server.schemas import LocalDeployment


class OpenAPIHandler:
    """Handler for merging deployment OpenAPI schemas into the agent API schema."""

    def __init__(self, model_server_handler: ModelServerHandler) -> None:
        """Initialize the OpenAPI handler.

        Args:
            model_server_handler: The model server handler for accessing deployments.
        """
        self.ms_handler = model_server_handler

    def _update_schema_refs(
        self,
        schema_obj: Any,
        deployment_id: str,
        original_schemas: set[str],
    ) -> Any:
        """Update schema references to use deployment-prefixed names.

        Args:
            schema_obj: The schema object to update.
            deployment_id: The deployment ID for prefixing.
            original_schemas: Set of original schema names.

        Returns:
            The updated schema object.
        """
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
                schema_obj[i] = self._update_schema_refs(
                    item, deployment_id, original_schemas
                )
        return schema_obj

    def _process_deployment_schemas(
        self,
        deployment: LocalDeployment,
        openapi_schema: dict[str, Any],
    ) -> dict[str, str] | None:
        """Process and add deployment schemas to the OpenAPI schema.

        Args:
            deployment: The local deployment to process.
            openapi_schema: The base OpenAPI schema to augment.

        Returns:
            Schema reference info if ComputeRequest exists, None otherwise.
        """
        if (
            not deployment.openapi_schema
            or "components" not in deployment.openapi_schema
        ):
            return None

        model_schema = deployment.openapi_schema
        if "schemas" not in model_schema["components"]:
            return None

        if "schemas" not in openapi_schema["components"]:
            openapi_schema["components"]["schemas"] = {}

        for schema_name, schema_def in model_schema["components"]["schemas"].items():
            self._add_prefixed_schema(
                openapi_schema,
                deployment.deployment_id,
                schema_name,
                schema_def,
                model_schema,
            )

        if "ComputeRequest" in model_schema["components"]["schemas"]:
            result: dict[str, str] = {
                "deployment_id": deployment.deployment_id,
                "schema_ref": (
                    f"#/components/schemas/"
                    f"Deployment{deployment.deployment_id}_ComputeRequest"
                ),
            }

            if "ComputeResponse" in model_schema["components"]["schemas"]:
                result["response_schema_ref"] = (
                    f"#/components/schemas/"
                    f"Deployment{deployment.deployment_id}_ComputeResponse"
                )

            return result
        return None

    def _add_prefixed_schema(
        self,
        openapi_schema: dict[str, Any],
        deployment_id: str,
        schema_name: str,
        schema_def: dict[str, Any],
        model_schema: dict[str, Any],
    ) -> None:
        """Add a deployment-prefixed schema to the OpenAPI schema.

        Args:
            openapi_schema: The base OpenAPI schema.
            deployment_id: The deployment ID for prefixing.
            schema_name: The original schema name.
            schema_def: The schema definition.
            model_schema: The model's OpenAPI schema.
        """
        prefixed_name = f"Deployment{deployment_id}_{schema_name}"

        updated_schema = self._update_schema_refs(
            copy.deepcopy(schema_def),
            deployment_id,
            set(model_schema["components"]["schemas"].keys()),
        )

        if isinstance(updated_schema, dict):
            title = updated_schema.get("title", schema_name)
            updated_schema["title"] = f"[Deployment {deployment_id}] {title}"
            if "description" not in updated_schema:
                updated_schema["description"] = f"Schema for deployment {deployment_id}"

        openapi_schema["components"]["schemas"][prefixed_name] = updated_schema

    @staticmethod
    def _update_compute_endpoint(
        openapi_schema: dict[str, Any],
        compute_schemas: list[dict[str, str]],
    ) -> None:
        """Update the compute endpoint with deployment-specific schemas.

        Args:
            openapi_schema: The OpenAPI schema to update.
            compute_schemas: List of compute schema info for each deployment.
        """
        compute_path = "/deployments/{deployment_id}/compute"
        if compute_path not in openapi_schema["paths"]:
            return

        if "post" not in openapi_schema["paths"][compute_path]:
            return

        openapi_schema["paths"][compute_path]["post"]["requestBody"] = {
            "content": {
                "application/json": {
                    "schema": {
                        "oneOf": [
                            {"$ref": schema["schema_ref"]} for schema in compute_schemas
                        ],
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
                                    "The response will match the deployment."
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

    def merge_deployment_schemas(
        self, openapi_schema: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge all deployment schemas into the base OpenAPI schema.

        Args:
            openapi_schema: The base OpenAPI schema.

        Returns:
            The augmented OpenAPI schema with all deployment schemas.
        """
        compute_schemas: list[dict[str, str]] = []

        with contextlib.suppress(Exception):
            for deployment in self.ms_handler.deployments.values():
                compute_schema_info = self._process_deployment_schemas(
                    deployment, openapi_schema
                )
                if compute_schema_info:
                    compute_schemas.append(compute_schema_info)

        if compute_schemas:
            self._update_compute_endpoint(openapi_schema, compute_schemas)

        return openapi_schema
