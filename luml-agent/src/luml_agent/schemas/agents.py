from pydantic import BaseModel

from luml_agent.services.agents import AgentDef


class AgentOut(BaseModel):
    id: str
    name: str
    cli: str
    prompt_flag: str
    auto_approve_flag: str
    resume_flag: str
    default_args: list[str]

    @classmethod
    def from_def(cls, a: AgentDef) -> "AgentOut":
        return cls(
            id=a.id,
            name=a.name,
            cli=a.cli,
            prompt_flag=a.prompt_flag,
            auto_approve_flag=a.auto_approve_flag,
            resume_flag=a.resume_flag,
            default_args=a.default_args,
        )
