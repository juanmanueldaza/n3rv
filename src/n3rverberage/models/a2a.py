from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, HttpUrl


class AgentSkill(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str


class AgentCapabilities(BaseModel):
    model_config = ConfigDict(frozen=True)

    streaming: bool = True


class NervAgentCard(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    url: HttpUrl
    version: str
    capabilities: AgentCapabilities
    skills: list[AgentSkill]


class TaskState(StrEnum):
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
