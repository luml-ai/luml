from promptopt.dataclasses import LLMExample


class Trace:
    def __init__(self):
        self._examples: dict[int, list[LLMExample]] = {}

    def add_example(self, key: object, input: str, output: str):
        if id(key) not in self._examples:
            self._examples[id(key)] = []
        self._examples[id(key)].append(LLMExample(input, output))

    def __repr__(self) -> str:
        str_ = "Trace:"
        for key, examples in self._examples.items():
            str_ += f"\n\t{key}:"
            for example in examples:
                str_ += f"\n\t\t{example.input} -> {example.output}"
        return str_
