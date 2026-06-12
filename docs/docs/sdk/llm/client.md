<a id="luml.llm._client"></a>

# luml.llm._client

<a id="luml.llm._client.LLMClient"></a>

## LLMClient Objects

```python
@runtime_checkable
class LLMClient(Protocol)
```

Protocol for LLM clients. Any object with this method signature works.

<a id="luml.llm._client.LLMClient.complete"></a>

#### complete

```python
def complete(system_prompt: str, user_prompt: str) -> str
```

Send a prompt to an LLM and return the raw text response.

<a id="luml.llm._client.OpenAIClient"></a>

## OpenAIClient Objects

```python
class OpenAIClient()
```

LLM client backed by the OpenAI chat-completions API.

Works with any OpenAI-compatible endpoint. Requires the ``openai`` package
(install via ``pip install luml_sdk[llm]``).

```python
from luml.llm import OpenAIClient
client = OpenAIClient(model="gpt-4.1-mini", temperature=0.0)
client = OpenAIClient(base_url="http://localhost:8080/v1")
```


