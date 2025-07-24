import asyncio
import httpx
from abc import ABC, abstractmethod


class LLM(ABC):
    provider_name: str

    @abstractmethod
    async def generate(self, messages: list, out_schema) -> str:
        pass

    @abstractmethod
    async def batch_generate(
        self,
        messages: list,
        temperature: float = 0.0,
        n_responses: int = 1,
    ) -> list[str]:
        pass

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 1.0,
        response_format: dict | None = None,
        **kwargs,
    ) -> dict[str, str]:
        raise NotImplementedError()


class OpenAIProvider(LLM):
    provider_name = "openai"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com",
        model="gpt-4o-mini",
        max_parallel_requests: int = 16,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self._semaphore = asyncio.Semaphore(max_parallel_requests)

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        response_format: dict | None = None,
        **kwargs,
    ) -> dict[str, str]:
        url = f"{self.base_url}/v1/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "response_format": response_format,
            "stream": False,
            **kwargs,
        }

        async with self._semaphore:
            async with httpx.AsyncClient() as client:
                retries = 3
                for attempt in range(retries):
                    try:
                        response = await client.post(
                            url, json=payload, headers=headers, timeout=60.0
                        )
                        response.raise_for_status()
                        return response.json()
                    except httpx.HTTPStatusError as e:
                        print(
                            "Attempt",
                            attempt + 1,
                            "failed with status code:",
                            e.response.status_code,
                        )
                        if attempt >= retries - 1:
                            print("Response Text:", e.response.text)
                            raise
                        await asyncio.sleep(delay=2**attempt)
        raise RuntimeError("Failed to get a valid response after multiple attempts.")

    async def generate(self, messages: list, out_schema) -> str:
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "OutputSchema",
                "schema": out_schema.model_json_schema(),
                "strict": True,
            },
        }

        out = await self.chat(
            model=self.model, messages=messages, response_format=response_format
        )

        return out["choices"][0]["message"]["content"]  # type: ignore

    async def batch_generate(
        self, messages: list, temperature: float = 0, n_responses: int = 1
    ):
        out = await self.chat(
            model=self.model,
            messages=messages,
            temperature=temperature,
            n=n_responses,
        )

        return [
            out["choices"][i]["message"]["content"]  # type: ignore
            for i in range(len(out["choices"]))
        ]


class OllamaProvider(LLM):
    provider_name = "ollama"
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2:1b"):
        self.base_url = base_url
        self.model = model

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        response_format: dict | None = None,
        **kwargs,
    ) -> dict[str, str]:
        url = f"{self.base_url}/api/chat"

        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "format": response_format,
            "options": {
                "temperature": temperature,
                **kwargs,
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()

    async def generate(self, messages: list, out_schema) -> str:

        out = await self.chat(
            model=self.model, messages=messages, response_format=out_schema.model_json_schema()
        )
        
        return out["message"]["content"]  # type: ignore

    async def batch_generate(
            self,
            messages: list,
            temperature: float = 0.0,
            n_responses: int = 1,
    ) -> list[str]:
        tasks = []
        for _ in range(n_responses):
            task = self.chat(
                model=self.model,
                messages=messages,
                temperature=temperature
            )
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        return [resp["message"]["content"] for resp in responses]


async def openai_provider_structured():
    api_key = "api_key"
    provider = OpenAIProvider(api_key=api_key)

    math_schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "math_reasoning",
            "schema": {
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "explanation": {"type": "string"},
                                "output": {"type": "string"},
                            },
                            "required": ["explanation", "output"],
                            "additionalProperties": False,
                        },
                    },
                    "final_answer": {"type": "string"},
                },
                "required": ["steps", "final_answer"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }

    response = await provider.chat(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": "Solve this math problem step by step: If a train travels at 120 km/h and covers a distance of 450 km, how long does the journey take in hours and minutes?",
            }
        ],
        temperature=0.2,
        response_format=math_schema,
    )

    return response


async def call_ollama_chat():
    provider = OllamaProvider()

    response = await provider.chat(
        model="llama3.2:1b",
        messages=[
            {
                "role": "user",
                "content": "Ollama is 22 years old and busy saving the world.",
            }
        ],
        temperature=0,
        response_format={
            "type": "object",
            "properties": {
                "age": {"type": "integer"},
                "available": {"type": "boolean"},
            },
            "required": ["age", "available"],
        },
        stream=False,
    )

    return response


async def make_test_ollama_methods():
    provider = OllamaProvider()
    
    class MockSchema:
        def model_json_schema(self):
            return {
                "type": "object",
                "properties": {
                    "sentiment": {"type": "string"},
                    "confidence": {"type": "number"}
                },
                "required": ["sentiment", "confidence"]
            }
    
    messages = [
        {
            "role": "user",
            "content": "Analyze sentiment: 'I love this product!'"
        }
    ]

    result = await provider.generate(messages, MockSchema())

    simple_messages = [
        {
            "role": "user",
            "content": "Solve this math problem step by step: If a train travels at 120 km/h and covers a distance of 450 km, how long does the journey take in hours and minutes?",
        }
    ]
    batch_results = await provider.batch_generate(simple_messages, temperature=0.1, n_responses=2)

    return result, batch_results


# if __name__ == "__main__":
#     result = asyncio.run(openai_provider_structured())
#     print(result)
#
#     result = asyncio.run(call_ollama_chat())
#     print(result)
#
#     result, batch_results = asyncio.run(make_test_ollama_methods())
#     print(result)
#     print(batch_results)
