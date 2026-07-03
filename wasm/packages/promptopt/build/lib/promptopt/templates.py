NODE_SYSTEM_PROMPT_TEMPLATE = """You are provided with an input schema, an output schema and an instruction. Answer with a JSON matching the output schema.

Input schema:
{input_schema}

Output schema:
{output_schema}

Instruction:
{instruction}
"""


GRAPH_LLM_REPR_TEMPLATE = """=====
Nodes:

{nodes}
======
Edges:

{edges}
======
"""

NODE_LLM_REPR_TEMPLATE = """ID: {id}
Type: {type}
Inputs: {inputs}
Outputs: {outputs}
{hint}
"""
