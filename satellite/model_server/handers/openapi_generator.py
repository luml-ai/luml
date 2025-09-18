from typing import Any

from handers.model_handler import ModelHandler


class OpenAPIGenerator:
    def __init__(self, model_handler: ModelHandler):
        self.model_handler = model_handler

    @staticmethod
    def _response_401():
        return {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "error": {
                                "type": "string",
                                "example": "Missing API key",
                            }
                        },
                    }
                }
            },
        }

    @staticmethod
    def _response_403():
        return {
            "description": "Invalid API key",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "error": {
                                "type": "string",
                                "example": "Invalid API key",
                            }
                        },
                    }
                }
            },
        }

    @staticmethod
    def _response_500():
        return {
            "description": "Application Error",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "error": {
                                "type": "string",
                                "example": "Failed to load manifest: file not found",
                            }
                        },
                    }
                }
            },
        }

    @staticmethod
    def _response_502():
        return {
            "description": "Authorization check failed",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "error": {
                                "type": "string",
                                "example": "Authorization check failed",
                            }
                        },
                    }
                }
            },
        }

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

    def _inject_pydantic_schemas(self, openapi_schema: dict, request_model) -> None:
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

    def _transform_refs(self, obj: Any) -> Any:
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
            },
            "401": self._response_401(),
            "403": self._response_403(),
            "500": self._response_500(),
            "502": self._response_502(),
        }

        openapi_schema["paths"]["/compute"]["post"]["summary"] = "Run model inference"
        openapi_schema["paths"]["/compute"]["post"]["description"] = """
        The inputs should conform to the model's input specification as defined in the manifest.
        Dynamic attributes are optional key-value pairs for model configuration.
        For JSON inputs/outputs, shapes in Swagger UI will reflect any custom schemas found in dtypes.json.
        """
        openapi_schema["paths"]["/compute"]["post"]["tags"] = ["model"]
        openapi_schema["paths"]["/compute"]["post"]["security"] = [{"BearerAuth": []}]

    @staticmethod
    def _generate_manifest_schema(manifest: dict) -> dict:
        properties = {}

        if "inputs" in manifest:
            input_items = []
            for inp in manifest["inputs"]:
                input_prop = {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "example": inp.get("name", "")},
                        "dtype": {"type": "string", "example": inp.get("dtype", "")},
                    },
                }
                if "content_type" in inp:
                    input_prop["properties"]["content_type"] = {
                        "type": "string",
                        "example": inp["content_type"],
                    }
                if "shape" in inp:
                    input_prop["properties"]["shape"] = {
                        "type": "array",
                        "items": {"type": "integer"},
                        "example": inp["shape"],
                    }
                input_items.append(input_prop)

            properties["inputs"] = {
                "type": "array",
                "description": "Model input specifications",
                "items": {"anyOf": input_items} if input_items else {"type": "object"},
            }

        if "outputs" in manifest:
            output_items = []
            for out in manifest["outputs"]:
                output_prop = {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "example": out.get("name", "")},
                        "dtype": {"type": "string", "example": out.get("dtype", "")},
                    },
                }
                if "content_type" in out:
                    output_prop["properties"]["content_type"] = {
                        "type": "string",
                        "example": out["content_type"],
                    }
                output_items.append(output_prop)

            properties["outputs"] = {
                "type": "array",
                "description": "Model output specifications",
                "items": {"anyOf": output_items} if output_items else {"type": "object"},
            }

        if "dynamic_attributes" in manifest:
            attr_items = []
            for attr in manifest["dynamic_attributes"]:
                attr_prop = {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "example": attr.get("name", "")},
                    },
                }
                if "description" in attr:
                    attr_prop["properties"]["description"] = {
                        "type": "string",
                        "example": attr["description"],
                    }
                attr_items.append(attr_prop)

            properties["dynamic_attributes"] = {
                "type": "array",
                "description": "Dynamic model attributes",
                "items": {"anyOf": attr_items} if attr_items else {"type": "object"},
            }

        for key, value in manifest.items():
            if key not in ["inputs", "outputs", "dynamic_attributes"]:
                if isinstance(value, str):
                    properties[key] = {"type": "string", "example": value}
                elif isinstance(value, (int, float)):
                    properties[key] = {"type": "number", "example": value}
                elif isinstance(value, bool):
                    properties[key] = {"type": "boolean", "example": value}
                else:
                    properties[key] = {"type": "object"}

        return {"type": "object", "properties": properties}

    @staticmethod
    def openapi_html():
        return """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Model API - Documentation</title>
                <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@3.52.5/swagger-ui.css" />
                <style>
                    .swagger-ui .topbar { display: none; }
                </style>
            </head>
            <body>
                <div id="swagger-ui"></div>
                <script src="https://unpkg.com/swagger-ui-dist@3.52.5/swagger-ui-bundle.js"></script>
                <script>
                SwaggerUIBundle({
                    url: '/openapi.json',
                    dom_id: '#swagger-ui',
                    presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.presets.standalone]
                });
                </script>
            </body>
            </html>
            """

    def _add_healthz_endpoint(self, openapi_schema: dict) -> None:
        if "/healthz" not in openapi_schema.get("paths", {}):
            openapi_schema.setdefault("paths", {})
            openapi_schema["paths"]["/healthz"] = {
                "get": {
                    "summary": "Health Check",
                    "description": "Returns the health status of the service",
                    "tags": ["health"],
                    "responses": {
                        "200": {
                            "description": "Service is healthy",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {
                                                "type": "string",
                                                "example": "healthy",
                                                "description": "Health status",
                                            }
                                        },
                                        "required": ["status"],
                                    }
                                }
                            },
                        }
                    },
                }
            }

    def _add_manifest_endpoint(self, openapi_schema: dict, manifest_schema: dict) -> None:
        if "/manifest" not in openapi_schema.get("paths", {}):
            openapi_schema.setdefault("paths", {})
            openapi_schema["paths"]["/manifest"] = {
                "get": {
                    "summary": "Get Model Manifest",
                    "description": "Returns the FNNX model manifest with input/output specifications and metadata",
                    "tags": ["model"],
                    "security": [{"BearerAuth": []}],
                    "responses": {
                        "200": {
                            "description": "Model manifest information",
                            "content": {"application/json": {"schema": manifest_schema}},
                        },
                        "401": self._response_401(),
                        "403": self._response_403(),
                        "500": self._response_500(),
                        "502": self._response_502(),
                    },
                }
            }

    def get_openapi_schema(
        self, title, version, description, routes=None, route_metadata=None
    ) -> dict[str, Any]:
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

    def generate_schema(self, title: str, version: str, description: str) -> dict[str, Any]:
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

        manifest_schema = self._generate_manifest_schema(manifest)

        self._inject_pydantic_schemas(openapi_schema, request_model)
        self._inject_dtype_schemas(openapi_schema, dtypes_schemas)
        self._update_input_references(openapi_schema, manifest, dtypes_schemas)
        self._add_healthz_endpoint(openapi_schema)
        self._add_manifest_endpoint(openapi_schema, manifest_schema)
        self._add_compute_endpoint(openapi_schema, manifest, dtypes_schemas)
        self._add_security_schemes(openapi_schema)

        return openapi_schema
