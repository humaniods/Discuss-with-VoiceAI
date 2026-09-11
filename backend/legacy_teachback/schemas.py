"""
Pydantic models. These are the exact contracts from
ExamPilot_Voice_Hackathon_MVP.md section 15.2, plus a `session_id` field
threaded through every tool payload so the backend can push results back to
the right browser tab over SSE (the plan didn't need this because it assumed
the tool call and the UI update happen in the same process; here, AssemblyAI's
servers call these tools over HTTP, so we need an explicit correlation id).
"""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

Understanding = Literal["clear", "partial", "memorized", "misconception", "needs_clarification"]


# ---- prepare_topic ---------------------------------------------------------

class PrepareTopicIn(BaseModel):
    session_id: str
    topic: str


class TopicMap(BaseModel):
    topic: str
    clarified_topic: str
    core_points: List[str]
    key_connections: List[str]
    common_misconceptions: List[str]
    probe_candidates: List[str]
    application_prompt: str


# ---- analyze_teachback ------------------------------------------------------

class AnalyzeTeachbackIn(BaseModel):
    session_id: str
    topic_map: TopicMap
    explanation: str
    probe_answers: List[str] = Field(default_factory=list)


class AnalyzeTeachbackOut(BaseModel):
    topic: str
    understanding: Understanding
    covered_points: List[str]
    missing_connections: List[str]
    misconceptions: List[str]
    evidence_quote: str
    next_explanation: str
    spoken_feedback: str


# ---- show_understanding_map -------------------------------------------------

class ShowUnderstandingMapIn(BaseModel):
    session_id: str
    result: AnalyzeTeachbackOut


class UnderstandingMapOut(BaseModel):
    screen: Literal["understanding_map"] = "understanding_map"
    topic: str
    understanding: Understanding
    summary: str
    missing_link: str
    evidence: str
    correction: str


# ---- misc --------------------------------------------------------------

class TokenOut(BaseModel):
    token: str
    agent_id: Optional[str] = None
    mock: bool = False
    expires_in_seconds: int = 300
