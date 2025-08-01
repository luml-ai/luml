from dfs_webworker.prompt_optimization.jsdata import JsData, Provider, Field as JSField

from promptopt.dataclasses import Field as NativeField
from promptopt.graph import Graph, BaseNode, InputNode, OutputNode, Processor, Gate
from promptopt.llm import OpenAIProvider, OllamaProvider, LLM
from promptopt.dataclasses import Example


def data_to_examples(
    data: dict[str, list] | None, inputs: list[str], outputs: list[str]
) -> list[Example]:
    if data is None:
        return []

    num_rows = len(next(iter(data.values()), []))
    examples = []

    for i in range(num_rows):
        row = {key: data[key][i] for key in data if i < len(data[key])}
        input_dict = {k: row[k] for k in inputs if k in row}
        output_dict = {k: row[k] for k in outputs if k in row}
        examples.append(Example(input=input_dict, output=output_dict))

    return examples


def convert_js_field(js_field: JSField) -> NativeField:
    return NativeField(
        name=js_field.value,
        type=js_field.type or "string",
        is_variadic=js_field.variadic,
        allowed_values=None,
    )


def init_llm(provider: Provider) -> LLM:
    if provider.provider_id == "openAi":
        if not provider.provider_settings.api_key:
            raise ValueError("API key is required for OpenAI provider")
        return OpenAIProvider(
            api_key=provider.provider_settings.api_key,
            model=provider.model_id,
        )
    if provider.provider_id == "ollama":
        base_url = provider.provider_settings.api_base or 'http://localhost:11434'
        return OllamaProvider(
            base_url=base_url,
            model=provider.model_id,
        )


def jsdata_to_graph(js_data: JsData) -> Graph:
    graph = Graph()
    node_map: dict[str, BaseNode] = {}

    print(JsData)

    for node in js_data.data.nodes:
        node_type = node.data.type.lower()
        fields = node.data.fields

        if node_type == "input":
            node_obj = InputNode([convert_js_field(f) for f in fields])

        elif node_type == "output":
            node_obj = OutputNode([convert_js_field(f) for f in fields])

        elif node_type == "processor":
            input_fields = [convert_js_field(f) for f in fields if f.variant == "input"]
            output_fields = [
                convert_js_field(f) for f in fields if f.variant == "output"
            ]
            node_obj = Processor(input_fields, output_fields)

        elif node_type == "gate":
            classification_fields = [
                convert_js_field(f) for f in fields if f.variant == "output"
            ]
            if len(classification_fields) != 1:
                raise ValueError(
                    f"Gate node {node.id} must have exactly one classification field"
                )
            output_classes = [f.value for f in fields if f.variant == "condition"]
            node_obj = Gate(
                classification_field=classification_fields[0],
                output_classes=output_classes,
            )

        else:
            raise ValueError(f"Unknown node type: {node.data.type}")

        if node.data.hint:
            node_obj.hint = node.data.hint

        print("adding node", node.id, node_type)
        graph.add_node(node_obj, node_name=node.id)
        node_map[node.id] = node_obj

    for edge in js_data.data.edges:
        lhs_node = node_map[edge.source_node]
        rhs_node = node_map[edge.target_node]
        graph.connect(
            lhs_node, edge.source_field_name, rhs_node, edge.target_field_name
        )

    return graph
