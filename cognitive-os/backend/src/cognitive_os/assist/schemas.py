from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PersonalTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=8000)
    priority: int = Field(default=3, ge=1, le=5)
    due_at: datetime | None = None
    remind_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)


class PersonalTaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    status: Literal["pending", "in_progress", "done", "cancelled"] | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    due_at: datetime | None = None
    remind_at: datetime | None = None
    tags: list[str] | None = None


class PersonalTaskView(BaseModel):
    id: str
    user_id: str
    title: str
    description: str | None
    status: str
    priority: int
    due_at: datetime | None
    remind_at: datetime | None
    completed_at: datetime | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class PersonalNoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=400)
    body_markdown: str = Field(default="", max_length=200_000)
    tags: list[str] = Field(default_factory=list)


class PersonalNoteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=400)
    body_markdown: str | None = Field(default=None, max_length=200_000)
    tags: list[str] | None = None


class PersonalNoteView(BaseModel):
    id: str
    user_id: str
    title: str
    body_markdown: str
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class PersonalNoteSearchHit(BaseModel):
    note_id: str
    title: str
    snippet: str
    tags: list[str]
    score: float | None = None
