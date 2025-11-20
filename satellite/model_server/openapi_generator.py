from typing import Any


class OpenAPIGenerator:
    def __init__(
        self,
        title: str = "Model API",
        version: str = "0.1.0",
        description: str = "model api",
        *,
        manifest: dict | None = None,
        dtypes_schemas: dict | None = None,
        request_schema: dict | None = None,
        response_schema: dict | None = None,
    ) -> None:
        self.title = title
        self.version = version
        self.description = description
        self.manifest = manifest
        self.dtypes_schemas = dtypes_schemas
        self.request_schema = request_schema
        self.response_schema = response_schema

    def _inject_dtype_schemas(self, openapi_schema: dict, dtypes_schemas: dict) -> None:
        for dtype_name, schema in dtypes_schemas.items():
            schema_copy = schema.copy()
            if "$defs" in schema_copy:
                for def_name, def_schema in schema_copy["$defs"].items():
                    transformed_def = self._transform_refs(def_schema.copy())
                    openapi_schema["components"]["schemas"][def_name] = transformed_def
                del schema_copy["$defs"]
            transformed_schema = self._transform_refs(schema_copy)
            openapi_schema["components"]["schemas"][dtype_name] = transformed_schema

    @staticmethod
    def _update_input_references(
        openapi_schema: dict, manifest: dict, dtypes_schemas: dict
    ) -> None:
        inputs_schema = openapi_schema["components"]["schemas"].get("InputsModel")
        if inputs_schema and "properties" in inputs_schema:
            for input_spec in manifest.get("inputs", []):
                name = input_spec["name"]
                dtype = input_spec.get("dtype")
                if input_spec.get("content_type") == "JSON" and dtype in dtypes_schemas:
                    inputs_schema["properties"][name] = {"$ref": f"#/components/schemas/{dtype}"}

    @staticmethod
    def _update_output_references(
        openapi_schema: dict, manifest: dict, dtypes_schemas: dict
    ) -> None:
        compute_response = openapi_schema["components"]["schemas"].get("ComputeResponse")
        if compute_response and "properties" in compute_response:
            for output_spec in manifest.get("outputs", []):
                name = output_spec["name"]
                dtype = output_spec.get("dtype")
                if output_spec.get("content_type") == "JSON" and dtype in dtypes_schemas:
                    compute_response["properties"][name] = {"$ref": f"#/components/schemas/{dtype}"}

        outputs_schema = openapi_schema["components"]["schemas"].get("OutputsModel")
        if outputs_schema and "properties" in outputs_schema:
            for output_spec in manifest.get("outputs", []):
                name = output_spec["name"]
                dtype = output_spec.get("dtype")
                if output_spec.get("content_type") == "JSON" and dtype in dtypes_schemas:
                    outputs_schema["properties"][name] = {"$ref": f"#/components/schemas/{dtype}"}

    @staticmethod
    def _add_security_schemes(openapi_schema: dict) -> None:
        openapi_schema["components"]["securitySchemes"] = {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "Authorization",
                "description": "Authorization: Bearer your_api_key_here",
            }
        }
        openapi_schema["security"] = [{"ApiKeyAuth": []}]

    def _inject_compute_request_schema(self, openapi_schema: dict, request_schema: Any) -> None:  # noqa: ANN401
        if "components" not in openapi_schema:
            openapi_schema["components"] = {}
        if "schemas" not in openapi_schema["components"]:
            openapi_schema["components"]["schemas"] = {}

        if "$defs" in request_schema:
            for def_name, def_schema in request_schema["$defs"].items():
                transformed_def = self._transform_refs(def_schema.copy())
                openapi_schema["components"]["schemas"][def_name] = transformed_def

        main_schema = {
            "type": "object",
            "properties": request_schema["properties"].copy(),
            "required": request_schema.get("required", []),
            "title": "ComputeRequest",
        }
        transformed_main = self._transform_refs(main_schema)
        openapi_schema["components"]["schemas"]["ComputeRequest"] = transformed_main

    def _inject_compute_response_schema(self, openapi_schema: dict, response_schema: Any) -> None:  # noqa: ANN401
        if "components" not in openapi_schema:
            openapi_schema["components"] = {}
        if "schemas" not in openapi_schema["components"]:
            openapi_schema["components"]["schemas"] = {}

        if "$defs" in response_schema:
            for def_name, def_schema in response_schema["$defs"].items():
                transformed_def = self._transform_refs(def_schema.copy())
                openapi_schema["components"]["schemas"][def_name] = transformed_def

        main_schema = {
            "type": "object",
            "properties": response_schema["properties"].copy(),
            "required": response_schema.get("required", []),
            "title": "ComputeResponse",
        }
        transformed_main = self._transform_refs(main_schema)
        openapi_schema["components"]["schemas"]["ComputeResponse"] = transformed_main

    def _transform_refs(self, obj: Any) -> Any:  # noqa: ANN401
        if isinstance(obj, dict):
            if "$ref" in obj and obj["$ref"].startswith("#/$defs/"):
                ref_name = obj["$ref"].replace("#/$defs/", "")
                obj["$ref"] = f"#/components/schemas/{ref_name}"
            else:
                for key, value in obj.items():
                    obj[key] = self._transform_refs(value)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                obj[i] = self._transform_refs(item)
        return obj

    @staticmethod
    def _add_compute_endpoint(openapi_schema: dict) -> None:
        openapi_schema.setdefault("paths", {})
        if "/compute" not in openapi_schema["paths"]:
            openapi_schema["paths"]["/compute"] = {}
        if "post" not in openapi_schema["paths"]["/compute"]:
            openapi_schema["paths"]["/compute"]["post"] = {}

        openapi_schema["paths"]["/compute"]["post"]["requestBody"] = {
            "content": {
                "application/json": {"schema": {"$ref": "#/components/schemas/ComputeRequest"}}
            },
            "required": True,
        }

        openapi_schema["paths"]["/compute"]["post"]["responses"] = {
            "200": {
                "description": "Successful response",
                "content": {
                    "application/json": {"schema": {"$ref": "#/components/schemas/ComputeResponse"}}
                },
            }
        }

        openapi_schema["paths"]["/compute"]["post"]["summary"] = "Run model inference"
        openapi_schema["paths"]["/compute"]["post"]["description"] = """
        The inputs should conform to the model's input specification as defined in the manifest.
        Dynamic attributes are optional key-value pairs for model configuration.
        For JSON inputs/outputs, shapes in Swagger UI
        will reflect any custom schemas found in dtypes.json.
        """
        openapi_schema["paths"]["/compute"]["post"]["tags"] = ["model"]
        openapi_schema["paths"]["/compute"]["post"]["security"] = [{"ApiKeyAuth": []}]

    def get_simple_schema(self) -> dict:
        return {
            "openapi": "3.0.0",
            "info": {
                "title": self.title,
                "version": self.version,
                "description": self.description,
            },
            "paths": {},
            "components": {"schemas": {}},
        }

    def get_openapi_schema(self) -> dict[str, Any]:  # noqa: ANN401
        if not self.manifest or not self.dtypes_schemas or not self.request_schema:
            return self.get_simple_schema()

        try:
            openapi_schema = {
                "openapi": "3.0.0",
                "info": {
                    "title": self.title,
                    "version": self.version,
                    "description": self.description,
                },
                "paths": {},
                "components": {
                    "schemas": {},
                    "securitySchemes": {
                        "ApiKeyAuth": {
                            "type": "apiKey",
                            "in": "header",
                            "name": "Authorization",
                            "description": "Authorization: Bearer your_api_key_here",
                        }
                    },
                },
            }

            self._inject_compute_request_schema(openapi_schema, self.request_schema)
            if self.response_schema:
                self._inject_compute_response_schema(openapi_schema, self.response_schema)
            self._inject_dtype_schemas(openapi_schema, self.dtypes_schemas)
            self._update_input_references(openapi_schema, self.manifest, self.dtypes_schemas)
            self._update_output_references(openapi_schema, self.manifest, self.dtypes_schemas)
            self._add_compute_endpoint(openapi_schema)

            return openapi_schema
        except Exception:
            return self.get_simple_schema()
