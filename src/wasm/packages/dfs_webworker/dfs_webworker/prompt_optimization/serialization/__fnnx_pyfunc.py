#### This code is injected into the __fnnx_autogen_content.py file; DO NOT UNCOMMENT!
# from fnnx.variants.pyfunc import PyFunc


# class GraphPyFunc(PyFunc):
#     def warmup(self):
#         self.graph_spec = self.fnnx_context.get_value("graph")
#         if not isinstance(self.graph_spec, dict):
#             raise ValueError("Graph spec must be a dictionary")
#         self.provider = self.fnnx_context.get_value("provider")
#         self.graph = Graph.from_dict(self.graph_spec)
#
#     def _get_client(self, dynamic_attributes: dict):
#         if self.provider == "openai":
#             api_key = dynamic_attributes.get("api_key")
#             if not isinstance(api_key, str):
#                 raise ValueError("API key must be a string")
#             model_id = self.fnnx_context.get_value("model_id")
#             if not isinstance(model_id, str):
#                 raise ValueError(
#                     f"Model ID must be a string, got {type(model_id)} :: {model_id}"
#                 )
#             return OpenAIProvider(model=model_id, api_key=api_key)
#         elif self.provider == "ollama":
#             base_url = dynamic_attributes.get("base_url")
#             if not isinstance(base_url, str):
#                 raise ValueError("Base url must be a string")
#             model_id = self.fnnx_context.get_value("model_id")
#             if not isinstance(model_id, str):
#                 raise ValueError(
#                     f"Model ID must be a string, got {type(model_id)} :: {model_id}"
#                 )
#             return OllamaProvider(model=model_id, base_url=base_url)
#         else:
#             raise ValueError(f"Unknown provider: {self.provider}")
#
#     def compute(self, inputs: dict, dynamic_attributes: dict) -> dict:
#         raise NotImplementedError("Only async compute is supported")
#
#     async def compute_async(self, inputs: dict, dynamic_attributes: dict) -> dict:
#         client = self._get_client(dynamic_attributes)
#         return {"out": await self.graph.run(inputs["in"], client)}
