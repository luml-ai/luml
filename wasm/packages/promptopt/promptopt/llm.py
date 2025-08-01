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

        async with httpx.AsyncClient(timeout=300.0) as client:
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


