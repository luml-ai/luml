from typing import Any

from handlers.model_handler import ModelHandler


class OpenAPIGenerator:
    def __init__(self, model_handler: ModelHandler) -> None:
        self.model_handler = model_handler

    @staticmethod
    def _inject_dtype_schemas(openapi_schema: dict, dtypes_schemas: dict) -> None:
        for dtype_name, schema in dtypes_schemas.items():
            openapi_schema["components"]["schemas"][dtype_name] = schema

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
    def _build_response_properties(manifest: dict, dtypes_schemas: dict) -> dict:
        resp_properties = {}
        for out_spec in manifest.get("outputs", []):
            oname = out_spec["name"]
            odtype = out_spec.get("dtype")
            if out_spec.get("content_type") == "JSON" and odtype in dtypes_schemas:
                resp_properties[oname] = {"$ref": f"#/components/schemas/{odtype}"}
            else:
                resp_properties[oname] = {"type": "object"}
        return resp_properties

    @staticmethod
    def _add_security_schemes(openapi_schema: dict) -> None:
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        }
        openapi_schema["security"] = [{"BearerAuth": []}]

    def _inject_pydantic_schemas(self, openapi_schema: dict, request_model: Any) -> None:  # noqa: ANN401
        request_schema = request_model.model_json_schema()

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

    def _add_compute_endpoint(
        self, openapi_schema: dict, manifest: dict, dtypes_schemas: dict
    ) -> None:
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

        resp_properties = self._build_response_properties(manifest, dtypes_schemas)
        openapi_schema["paths"]["/compute"]["post"]["responses"] = {
            "200": {
                "description": "Successful response",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": resp_properties or {"result": {"type": "object"}},
                        }
                    }
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
        openapi_schema["paths"]["/compute"]["post"]["security"] = [{"BearerAuth": []}]

    def get_openapi_schema(self, title: str, version: str, description: str) -> dict[str, Any]:
        try:
            return self.generate_schema(
                title=title,
                version=version,
                description=description,
            )
        except Exception:
            return {
                "openapi": "3.0.0",
                "info": {
                    "title": title,
                    "version": version,
                    "description": description,
                },
                "paths": {},
                "components": {"schemas": {}},
            }

    def generate_schema(
        self, title: str = "Model API", version: str = "0.1.0", description: str = "model api"
    ) -> dict[str, Any]:
        manifest = self.model_handler.get_manifest()
        dtypes_schemas = self.model_handler.load_dtypes_schemas()

        request_model = self.model_handler.get_request_model()

        openapi_schema = {
            "openapi": "3.0.0",
            "info": {
                "title": title,
                "version": version,
                "description": description,
            },
            "paths": {},
            "components": {
                "schemas": {},
                "securitySchemes": {
                    "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
                },
            },
        }

        self._inject_pydantic_schemas(openapi_schema, request_model)
        self._inject_dtype_schemas(openapi_schema, dtypes_schemas)
        self._update_input_references(openapi_schema, manifest, dtypes_schemas)
        self._add_compute_endpoint(openapi_schema, manifest, dtypes_schemas)

        return openapi_schema
