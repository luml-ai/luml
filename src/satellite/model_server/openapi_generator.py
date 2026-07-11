import copy
from typing import Any


class OpenAPIGenerator:
    def __init__(
        self,
        title: str = "Model API",
        version: str = "0.1.0",
        description: str = "Model API",
        *,
        manifest: dict,
        dtypes_schemas: dict,
    ) -> None:
        self.title = title
        self.version = version
        self.description = description
        self.manifest = manifest
        self.dtypes_schemas = dtypes_schemas

        self.schema = self.get_simple_schema()

        self.request_schema = None
        self.response_schema = None

    def get_simple_schema(self) -> dict[str, Any]:  # noqa: ANN401
        return {
            "openapi": "3.0.0",
            "info": {
                "title": self.title,
                "version": self.version,
                "description": self.description,
            },
            "paths": {},
            "components": {
                "schemas": {},
                "securitySchemes": self.security_schema,
            },
        }

    @property
    def security_schema(self) -> dict[str, dict[str, str]]:
        return {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "Authorization",
                "description": "Authorization: Bearer your_api_key_here",
            }
        }

    @property
    def components_schemas(self) -> dict[str, Any]:  # noqa: ANN401
        return self.schema["components"]["schemas"]

    @components_schemas.setter
    def components_schemas(self, value: dict[str, Any]) -> None:
        self.schema["components"]["schemas"] = value

    @property
    def paths(self) -> dict[str, Any]:  # noqa: ANN401
        return self.schema["paths"]

    @staticmethod
    def _get_primitive_json_schema(dtype: str) -> dict[str, Any]:  # noqa: ANN401
        type_map = {
            "string": {"type": "string"},
            "integer": {"type": "integer"},
            "int": {"type": "integer"},
            "int32": {"type": "integer"},
            "int64": {"type": "integer"},
            "float": {"type": "number"},
            "float32": {"type": "number"},
            "float64": {"type": "number"},
            "boolean": {"type": "boolean"},
        }
        return type_map.get(dtype, {})

    @staticmethod
    def _wrap_in_arrays(base_schema: dict[str, Any], shape: list[int | str]) -> dict[str, Any]:  # noqa: ANN401
        result = base_schema
        for dim in reversed(shape):
            if isinstance(dim, str):
                result = {"type": "array", "items": result}
            elif isinstance(dim, int):
                result = {
                    "type": "array",
                    "items": result,
                    "minItems": dim,
                    "maxItems": dim,
                }
        return result

    @staticmethod
    def _extract_dtype_ref(dtype: str) -> str | None:
        if dtype.startswith("NDContainer[") and dtype.endswith("]"):
            return dtype[12:-1]
        return None

    def _get_json_schema_for_field(
        self, content_type: str, dtype: str, shape: list[int | str] | None = None
    ) -> dict[str, Any]:  # noqa: ANN401
        if content_type == "NDJSON":
            if dtype.startswith("Array["):
                inner = dtype[6:-1]
                base_schema = self._get_primitive_json_schema(inner)
            elif dtype.startswith("NDContainer["):
                base_schema = {"type": "object"}
            else:
                raise ValueError(f"Unsupported dtype for NDJSON: {dtype}")

            if shape:
                return self._wrap_in_arrays(base_schema, shape)
            else:
                return {"type": "array", "items": base_schema}

        elif content_type == "JSON":
            if dtype in self.dtypes_schemas:
                return {"$ref": f"#/components/schemas/{dtype}"}
            return {"type": "object"}

        return {}

    def _create_input_schema(self, manifest: dict) -> dict[str, Any]:  # noqa: ANN401
        properties = {}
        required = []

        for input_spec in manifest["inputs"]:
            name = input_spec["name"]
            dtype = input_spec["dtype"]
            content_type = input_spec["content_type"]
            description = input_spec.get("description", f"Input field of type {dtype}")

            field_schema = self._get_json_schema_for_field(
                content_type, dtype, shape=input_spec.get("shape", None)
            )
            field_schema["description"] = description

            properties[name] = field_schema
            required.append(name)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "title": "InputsModel",
        }

    @staticmethod
    def _create_dynamic_attributes_schema(manifest: dict) -> dict[str, Any]:  # noqa: ANN401
        properties = {}

        for attr in manifest.get("dynamic_attributes", []):
            name = attr["name"]
            title = " ".join(word.capitalize() for word in name.split("_"))
            properties[name] = {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "default": f"<<<{name}>>>",
                "description": attr.get("description", f"Dynamic attribute '{name}'"),
                "title": title,
            }

        return {
            "type": "object",
            "properties": properties,
            "title": "DynamicAttributesModel",
        }

    def _create_output_schema(self, manifest: dict) -> dict[str, Any]:  # noqa: ANN401
        properties = {}
        required = []

        for output_spec in manifest.get("outputs", []):
            dtype = output_spec["dtype"]
            description = output_spec.get("description", f"Output field of type {dtype}")

            field_schema = self._get_json_schema_for_field(
                output_spec["content_type"], dtype, shape=output_spec.get("shape", None)
            )
            field_schema["description"] = description

            properties[output_spec["name"]] = field_schema
            required.append(output_spec["name"])

        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "title": "OutputsModel",
        }

    def _get_response_model(self) -> None:
        self.response_schema = self._create_output_schema(self.manifest)

    def _get_request_model(self) -> None:
        input_schema = self._create_input_schema(self.manifest)
        dynamic_attrs_schema = self._create_dynamic_attributes_schema(self.manifest)

        input_schema_with_desc = {**input_schema, "description": "Input data for the model"}
        dynamic_attrs_schema_with_desc = {
            **dynamic_attrs_schema,
            "description": "Dynamic attributes",
        }

        self.request_schema = {
            "type": "object",
            "properties": {
                "inputs": input_schema_with_desc,
                "dynamic_attributes": dynamic_attrs_schema_with_desc,
            },
            "required": ["inputs", "dynamic_attributes"],
            "title": "ComputeRequest",
        }

    def _inject_dtype_schemas(self) -> None:
        for dtype_name, schema in self.dtypes_schemas.items():
            schema_copy = copy.deepcopy(schema)
            if "$defs" in schema_copy:
                for def_name, def_schema in schema_copy["$defs"].items():
                    transformed = self._transform_refs(copy.deepcopy(def_schema))
                    self.components_schemas[def_name] = transformed
                del schema_copy["$defs"]
            transformed_main = self._transform_refs(schema_copy)
            self.components_schemas[dtype_name] = transformed_main

    @staticmethod
    def _build_ndjson_schema_with_shape(dtype_ref: str, shape: list[int | str]) -> dict[str, Any]:  # noqa: ANN401
        base_schema = {"$ref": f"#/components/schemas/{dtype_ref}"}

        result = base_schema
        for dim in reversed(shape):
            if isinstance(dim, str):
                result = {"type": "array", "items": result}
            elif isinstance(dim, int):
                result = {
                    "type": "array",
                    "items": result,
                    "minItems": dim,
                    "maxItems": dim,
                }

        return result

    def _push_type_ref_schema(self, spec: dict[str, Any], response: dict[str, Any]) -> None:  # noqa: ANN401
        dtype = spec.get("dtype")
        content_type = spec.get("content_type")

        if content_type == "JSON" and dtype in self.dtypes_schemas:
            response["properties"][spec["name"]] = {"$ref": f"#/components/schemas/{dtype}"}

        elif content_type == "NDJSON":
            dtype_ref = self._extract_dtype_ref(dtype)
            if dtype_ref and dtype_ref in self.dtypes_schemas:
                shape = spec.get("shape")
                if shape:
                    response["properties"][spec["name"]] = self._build_ndjson_schema_with_shape(
                        dtype_ref, shape
                    )
                else:
                    response["properties"][spec["name"]] = {
                        "type": "array",
                        "items": {"$ref": f"#/components/schemas/{dtype_ref}"},
                    }

    def _update_input_references(self) -> None:
        inputs_schema = self.components_schemas.get("InputsModel")
        if inputs_schema and "properties" in inputs_schema:
            for input_spec in self.manifest.get("inputs", []):
                self._push_type_ref_schema(input_spec, inputs_schema)

    def _update_output_references(self) -> None:
        compute_response = self.components_schemas.get("ComputeResponse")
        if compute_response and "properties" in compute_response:
            for output_spec in self.manifest.get("outputs", []):
                self._push_type_ref_schema(output_spec, compute_response)

        outputs_schema = self.components_schemas.get("OutputsModel")
        if outputs_schema and "properties" in outputs_schema:
            for output_spec in self.manifest.get("outputs", []):
                self._push_type_ref_schema(output_spec, outputs_schema)

    def _init_components_structure(self) -> None:
        if "components" not in self.schema:
            self.schema["components"] = {}
        if "schemas" not in self.schema["components"]:
            self.components_schemas = {}

        if "$defs" in self.request_schema:
            for def_name, def_schema in self.request_schema["$defs"].items():
                self.components_schemas[def_name] = self._transform_refs(def_schema.copy())

    def _inject_compute_request_schema(self) -> None:  # noqa: ANN401
        self._init_components_structure()

        inputs_prop = self.request_schema["properties"]["inputs"]
        dynamic_attrs_prop = self.request_schema["properties"]["dynamic_attributes"]

        inputs_schema = {k: v for k, v in inputs_prop.items() if k != "description"}
        dynamic_attrs_schema = {k: v for k, v in dynamic_attrs_prop.items() if k != "description"}

        self.components_schemas["InputsModel"] = self._transform_refs(inputs_schema)
        self.components_schemas["DynamicAttributesModel"] = self._transform_refs(
            dynamic_attrs_schema
        )

        self.components_schemas["ComputeRequest"] = self._transform_refs(
            {
                "type": "object",
                "properties": {
                    "inputs": {
                        "$ref": "#/components/schemas/InputsModel",
                        "description": inputs_prop.get("description", "Input data for the model"),
                    },
                    "dynamic_attributes": {
                        "$ref": "#/components/schemas/DynamicAttributesModel",
                        "description": dynamic_attrs_prop.get("description", "Dynamic attributes"),
                    },
                },
                "required": self.request_schema.get("required", []),
                "title": "ComputeRequest",
            }
        )

    def _inject_compute_response_schema(self) -> None:  # noqa: ANN401
        self._init_components_structure()

        self.components_schemas["ComputeResponse"] = self._transform_refs(
            {
                "type": "object",
                "properties": self.response_schema["properties"].copy(),
                "required": self.response_schema.get("required", []),
                "title": "ComputeResponse",
            }
        )

    def _transform_refs(self, obj: Any) -> Any:  # noqa: ANN401
        if isinstance(obj, dict):
            if "$ref" in obj and obj["$ref"].startswith("#/$defs/"):
                obj["$ref"] = f"#/components/schemas/{obj['$ref'].replace('#/$defs/', '')}"
            else:
                for key, value in obj.items():
                    obj[key] = self._transform_refs(value)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                obj[i] = self._transform_refs(item)
        return obj

    def _add_compute_endpoint(self) -> None:
        self.schema.setdefault("paths", {})
        if "/compute" not in self.paths:
            self.paths["/compute"] = {}
        if "post" not in self.paths["/compute"]:
            self.paths["/compute"]["post"] = {}

        compute = self.paths["/compute"]["post"]

        compute["requestBody"] = {
            "content": {
                "application/json": {"schema": {"$ref": "#/components/schemas/ComputeRequest"}}
            },
            "required": True,
        }

        compute["responses"] = {
            "200": {
                "description": "Successful response",
                "content": {
                    "application/json": {"schema": {"$ref": "#/components/schemas/ComputeResponse"}}
                },
            }
        }

        compute["summary"] = "Run model inference"
        compute["description"] = None
        compute["tags"] = ["model"]
        compute["security"] = [{"ApiKeyAuth": []}]

    def get_openapi_schema(self) -> dict[str, Any]:  # noqa: ANN401
        if not self.manifest:
            return self.schema

        try:
            self._get_request_model()
            self._get_response_model()
            self._inject_compute_request_schema()
            if self.response_schema:
                self._inject_compute_response_schema()
            self._inject_dtype_schemas()
            self._update_input_references()
            self._update_output_references()
            self._add_compute_endpoint()
            return self.schema
        except Exception as e:
            print(f"Failed to generate OpenAPI schema: {e}")
            return self.get_simple_schema()
