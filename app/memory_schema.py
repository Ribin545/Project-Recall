"""
Project Recall — Memory Schema

Pydantic models for structured memory objects extracted from session transcripts.
Supports rich emotional metadata for emotion-aware memory selection.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class Emotion(BaseModel):
    primary: str = Field(
        ...,
        description="Primary emotion: anxiety, sadness, anger, shame, loneliness, overwhelm, uncertainty, hopefulness, relief, neutral"
    )
    secondary: List[str] = Field(default_factory=list)
    all_emotions: List[str] = Field(
        default_factory=list,
        description="All mapped emotions including primary + secondary"
    )
    intensity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Emotional intensity 0.0-1.0"
    )
    valence: Optional[float] = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Pleasure/displeasure: -1.0 (negative) to +1.0 (positive)"
    )
    arousal: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Activation level: 0.0 (calm) to 1.0 (activated)"
    )
    trajectory: Optional[str] = Field(
        default=None,
        description="Trajectory: worsening, unchanged, improving, resolved"
    )
    session_open_tone: Optional[str] = Field(
        default=None,
        description="Emotional tone at session start"
    )
    session_close_tone: Optional[str] = Field(
        default=None,
        description="Emotional tone at session end"
    )


class Memory(BaseModel):
    memory_id: str = Field(..., description="Unique memory identifier")
    user_id: str = Field(..., description="User identifier")
    source_session_id: str = Field(..., description="Session this memory came from")
    source_timestamp: str = Field(..., description="Session timestamp")
    memory_type: str = Field(
        ...,
        description="Type: communication_script, remembered_phrase, grounding_phrase, follow_up_intent, coping_strategy, unresolved_theme, recurring_theme, emotional_pattern, relationship_context, user_goal, preference, session_summary"
    )
    memory_source_kind: str = Field(
        default="key_moment",
        description="Source: key_moment, follow_up_topic, summary, exact_user_request"
    )
    theme: Optional[str] = Field(
        default=None,
        description="Session theme this memory belongs to"
    )
    source_text: Optional[str] = Field(
        default=None,
        description="Full source text (key_moment text, summary, or follow-up topic)"
    )
    summary: str = Field(..., description="Compact human-readable summary")
    exact_value: Optional[str] = Field(
        default=None,
        description="Exact text the user wants remembered, if applicable"
    )
    canonical_slot: Optional[str] = Field(
        default=None,
        description="Normalized canonical slot for deterministic exact lookup, e.g. grounding_phrase, communication_script, prep_plan"
    )
    topic_tags: List[str] = Field(default_factory=list)
    follow_up_topics: List[str] = Field(
        default_factory=list,
        description="Follow-up topics from the session"
    )
    risk_flags: List[str] = Field(
        default_factory=list,
        description="Risk flags from the session"
    )
    emotion: Emotion = Field(..., description="Emotion metadata")
    importance: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Importance score 0.0-1.0"
    )
    sensitivity: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Sensitivity score 0.0-1.0 — higher means more private"
    )
    resolved_status: str = Field(
        default="unresolved",
        description="resolved, unresolved, partially_resolved, unknown"
    )
    follow_up_recommended: bool = Field(
        default=False,
        description="Should this be followed up in next session?"
    )
    safe_to_reference_in_opener: bool = Field(
        default=True,
        description="Can this memory be used in a session-opening greeting?"
    )
    is_distractor: bool = Field(
        default=False,
        description="Is this memory a distractor for testing?"
    )
    is_canonical: bool = Field(
        default=False,
        description="Is this a canonical fact the user explicitly asked to remember?"
    )
    user_explicitly_asked_to_remember: bool = Field(
        default=False,
        description="Did the user explicitly ask the assistant to remember this?"
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence that this memory is the correct answer to a direct question"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    def to_embedding_text(self) -> str:
        """Format memory as rich embedding text for vector DB."""
        parts = [
            f"Memory type: {self.memory_type}.",
            f"Source kind: {self.memory_source_kind}.",
        ]
        if self.theme:
            parts.append(f"Theme: {self.theme}.")
        if self.source_text:
            parts.append(f"Source text: {self.source_text}")
        parts.append(f"Summary: {self.summary}")
        if self.topic_tags:
            parts.append(f"Topic tags: {', '.join(self.topic_tags)}")
        if self.follow_up_topics:
            parts.append(f"Follow-up topics: {', '.join(self.follow_up_topics)}")
        parts.append(f"Primary emotion: {self.emotion.primary}")
        if self.emotion.secondary:
            parts.append(f"Secondary emotions: {', '.join(self.emotion.secondary)}")
        if self.emotion.all_emotions:
            parts.append(f"All emotions: {', '.join(self.emotion.all_emotions)}")
        parts.append(f"Resolution: {self.resolved_status}")
        if self.exact_value:
            parts.append(f"Exact value: {self.exact_value}")
        if self.user_explicitly_asked_to_remember:
            parts.append("User explicitly asked to remember: yes")
        return ". ".join(parts) + "."
