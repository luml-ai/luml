from dataclasses import dataclass
from enum import Enum


class EvaluationModes(str, Enum):
    exact_match = "Exact match"
    llm_based = "LLM-based"
    none_ = "None"


@dataclass
class Field:
    id: str
    value: str
    variant: str
    type: str | None = None
    variadic: bool = False


@dataclass
class NodeData:
    fields: list[Field]
    type: str
    hint: str | None = None


@dataclass
class Node:
    id: str
    data: NodeData


@dataclass
class Edge:
    id: str
    source_node: str
    source_field: str
    source_field_name: str
    target_field_name: str
    target_node: str
    target_field: str


@dataclass
class GraphData:
    edges: list[Edge]
    nodes: list[Node]


@dataclass
class ProviderSettings:
    api_key: str | None = None
    organization: str | None = None
    api_base: str | None = None


@dataclass
class Provider:
    provider_id: str
    model_id: str
    provider_settings: ProviderSettings


@dataclass
class Settings:
    task_description: str
    teacher: Provider
    student: Provider
    evaluation_mode: EvaluationModes
    criteria_list: list[str]
    inputs: list[str]
    outputs: list[str]


@dataclass
class JsData:
    data: GraphData
    settings: Settings
    dataset: dict[str, list] | None = None  # TODO

    @classmethod
    def from_dict(cls, raw: dict) -> "JsData":
        print("Parsing JS data")

        def parse_field(field: dict) -> Field:
            return Field(**field)

        def parse_node_data(data: dict) -> NodeData:
            fields = [parse_field(f) for f in data["fields"]]
            return NodeData(fields=fields, type=data["type"], hint=data.get("hint"))

        def parse_node(node: dict) -> Node:
            return Node(id=node["id"], data=parse_node_data(node["data"]))

        def parse_edge(edge: dict) -> Edge:
            source_field_id = edge["sourceField"]
            target_field_id = edge["targetField"]

            def get_field_value(node_id: str, field_id: str) -> str:
                for node in raw["data"]["nodes"]:
                    if node["id"] == node_id:
                        for field in node["data"]["fields"]:
                            if field["id"] == field_id:
                                return field.get("value", "")
                return ""

            return Edge(
                id=edge["id"],
                source_node=edge["sourceNode"],
                source_field=source_field_id,
                target_node=edge["targetNode"],
                target_field=target_field_id,
                source_field_name=get_field_value(edge["sourceNode"], source_field_id),
                target_field_name=get_field_value(edge["targetNode"], target_field_id),
            )

        def parse_graph_data(data: dict) -> GraphData:
            edges = [parse_edge(e) for e in data["edges"]]
            nodes = [parse_node(n) for n in data["nodes"]]
            return GraphData(edges=edges, nodes=nodes)

        def parse_provider_settings(settings: dict) -> ProviderSettings:
            return ProviderSettings(
                api_key=settings.get("apiKey"),
                organization=settings.get("organization"),
                api_base=settings.get("apiBase"),
            )

        def parse_provider(provider: dict) -> Provider:
            return Provider(
                provider_id=provider["providerId"],
                model_id=provider["modelId"],
                provider_settings=parse_provider_settings(provider["providerSettings"]),
            )

        def parse_settings(settings: dict) -> Settings:
            return Settings(
                task_description=settings["taskDescription"],
                teacher=parse_provider(settings["teacher"]),
                student=parse_provider(settings["student"]),
                evaluation_mode=settings["evaluationMode"],
                criteria_list=settings["criteriaList"],
                inputs=settings.get("inputs", []),
                outputs=settings.get("outputs", []),
            )

        return cls(
            data=parse_graph_data(raw["data"]),
            settings=parse_settings(raw["settings"]),
            dataset=raw["trainingData"],
        )
