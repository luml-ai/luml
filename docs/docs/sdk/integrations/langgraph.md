<a id="luml.integrations.langgraph.packaging"></a>

# luml.integrations.langgraph.packaging

<a id="luml.integrations.langgraph.packaging.save_langgraph"></a>

#### save_langgraph

```python
def save_langgraph(
        graph: Pregel | Callable[[], Pregel] | str,
        path: str | None = None,
        dependencies: Literal["default"] | Literal["all"]
    | list[str] = "default",
        extra_dependencies: list[str] | None = None,
        extra_code_modules: list[str] | Literal["auto"] | None = "auto",
        env_vars: list[str] | None = None,
        manifest_model_name: str | None = None,
        manifest_model_version: str | None = None,
        manifest_model_description: str | None = None,
        manifest_extra_producer_tags: list[str] | None = None
) -> ModelReference
```

Save LangGraph application to LUML format for deployment.

Packages a LangGraph workflow with its dependencies, environment variables,
and metadata for production deployment or model registry.

**Arguments**:

- `graph` - LangGraph Pregel instance, callable returning Pregel, or import path string.
- `path` - Output file path. Auto-generated if not provided.
- `dependencies` - Dependency management strategy:
  - "default": Auto-detect dependencies
  - "all": Include all detected dependencies
  - list: Custom dependency list
- `extra_dependencies` - Additional pip packages to include.
- `extra_code_modules` - Local code modules to bundle.
  - "auto": Auto-detect local dependencies (default)
  - list: Specific modules to include
  - None: Don't include local modules
- `env_vars` - List of environment variable names to mark as runtime secrets.
- `manifest_model_name` - Model name for metadata.
- `manifest_model_version` - Model version for metadata.
- `manifest_model_description` - Model description for metadata.
- `manifest_extra_producer_tags` - Additional tags for model metadata.
  

**Returns**:

- `ModelReference` - Reference to the saved model package with embedded Mermaid diagram.
  

**Example**:

```python
from langgraph.graph import StateGraph
from luml.integrations.langgraph.packaging import save_langgraph

# Define your LangGraph
def create_graph():
    workflow = StateGraph(...)
    # ... add nodes and edges
    return workflow.compile()

graph = create_graph()

# Save graph
model_ref = save_langgraph(
    graph,
    path="my_agent.luml",
    env_vars=["OPENAI_API_KEY"],
    manifest_model_name="customer_support_agent",
    manifest_model_version="2.0.0"
)
```

