"""Building blocks shared by every console task (Offboarding, New employee, ...)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Status(str, Enum):
    OK = "Done"
    PARTIAL = "Partly done"
    FAILED = "Failed"
    SKIPPED = "Skipped"


@dataclass
class StepResult:
    step_id: str
    title: str
    status: Status
    detail: str = ""
    items: list[str] = field(default_factory=list)


@dataclass
class PlannedStep:
    step_id: str
    title: str
    actions: list[str]          # human-readable lines shown in the preview
    will_change: bool = True    # False if there is nothing to do


@dataclass
class TaskInfo:
    task_id: str
    title: str
    description: str
    available: bool = True      # False = shown in the sidebar as "coming soon"
