from promptopt.graph import Graph
from promptopt.llm import LLM
from promptopt.nodes.io import IONode

INSTRUCTION_PROPOSAL_PROMPT_TEMPLATE = """
You are an expert in prompt engineering. Your task is to generate an instruction for a single component of a compound AI system. The system is represented as a graph of nodes, where each node has its own function: 
- Input node: receives the input data, acts as an entry point to the system.
- Processor node: processes the data, produces the output based on the schema. 
- Gate node: acts as a classifier. Its result is used for directing the flow of data. The gate is unable to change the data, it can only classify it.
- Output node: produces the final output of the system, acts as an exit point.
{task_description}
Graph: 
{graph}

You are generating the instruction for node {node_id}. The instruction should be clear, concise, and problem-specific. 
The instruction produced by you will be injected into a larger instruction that already contains the information about the input and output schemas and generic function of the node, but unaware of any other nodes or the overall system. Instead of repeating this information, try to focus on the following:
1. Explain how the node should process the data, what are the steps it should take to produce the output from the first attempt.
2. Explain the overall purpose of the node in the system, what is its role and how it fits into the overall compound AI system. 

Take the following into account: 
1. The nodes are not aware of the other nodes, the purpose of the system or generic functions of the other nodes.
2. The nodes are only able to produce the output based on the schema and do not have access to any tools.
3. The communication between nodes is orchestrated by the external system, so the nodes cannot control the flow of data or the order of execution. Do not instruct the node to explicitly communicate with other nodes or to control the flow of data.

Your answer should contain the instruction only, without any additional text or explanation.

Instruction:
"""


async def propose_instructions(
    graph: Graph,
    llm: LLM,
    n_instructions: int = 1,
    task_description: str | None = None,
) -> dict[int, list[str]]:
    graph_repr = graph.llm_repr()

    proposals = {}

    for node in graph.nodes.values():
        if isinstance(node, IONode):
            continue
        proposal_prompt = INSTRUCTION_PROPOSAL_PROMPT_TEMPLATE.format(
            graph=graph_repr,
            node_id=id(node),
            task_description=f"\nTask description:\n`{task_description}`\n"
            if task_description
            else "",
        )

        ins = await llm.batch_generate(
            messages=[{"role": "user", "content": proposal_prompt}],
            n_responses=n_instructions,
            temperature=0.7,
        )

        proposals[id(node)] = ins

    return proposals
