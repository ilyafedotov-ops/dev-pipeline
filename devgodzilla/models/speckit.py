"""
DevGodzilla SpecKit Models

Pydantic models for SpecKit artifacts: specifications, plans, tasks.
These models provide type safety and validation for spec-driven development.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Priority(str, Enum):
    """Task/story priority levels."""
    P1 = "P1"  # Must have
    P2 = "P2"  # Should have
    P3 = "P3"  # Could have
    P4 = "P4"  # Won't have (this time)


class TaskStatus(str, Enum):
    """Task completion status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class UserStory(BaseModel):
    """A user story in a feature specification."""
    id: str = Field(..., description="Story ID (e.g., US1, US2)")
    priority: Priority = Field(default=Priority.P2)
    title: str
    description: Optional[str] = None
    acceptance_criteria: List[str] = Field(default_factory=list)


class FunctionalRequirement(BaseModel):
    """A functional requirement in a specification."""
    id: str = Field(..., description="Requirement ID (e.g., FR-001)")
    description: str
    needs_clarification: bool = False
    clarification_notes: Optional[str] = None


class FeatureSpec(BaseModel):
    """A feature specification document."""
    title: str
    overview: str
    user_stories: List[UserStory] = Field(default_factory=list)
    functional_requirements: List[FunctionalRequirement] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TechnicalContext(BaseModel):
    """Technical context for an implementation plan."""
    language: str = "Python 3.11+"
    framework: Optional[str] = None
    testing: str = "pytest"
    storage: Optional[str] = None
    target_platform: Optional[str] = None
    performance_goals: Optional[str] = None
    constraints: List[str] = Field(default_factory=list)


class PlanPhase(BaseModel):
    """A phase in an implementation plan."""
    name: str
    description: Optional[str] = None
    tasks: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)


class ImplementationPlan(BaseModel):
    """An implementation plan document."""
    title: str
    goal: str
    technical_context: TechnicalContext = Field(default_factory=TechnicalContext)
    phases: List[PlanPhase] = Field(default_factory=list)
    verification_plan: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Task(BaseModel):
    """A task in a task list."""
    id: str = Field(..., description="Task ID (e.g., T001)")
    description: str
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    parallelizable: bool = Field(default=False, description="Can run concurrently with other [P] tasks")
    user_story_id: Optional[str] = Field(default=None, description="Related user story (e.g., US1)")
    file_paths: List[str] = Field(default_factory=list, description="Files to modify")
    dependencies: List[str] = Field(default_factory=list, description="Task IDs this depends on")


class TaskPhase(BaseModel):
    """A phase containing multiple tasks."""
    name: str
    description: Optional[str] = None
    tasks: List[Task] = Field(default_factory=list)


class TaskList(BaseModel):
    """A task list document."""
    title: str
    phases: List[TaskPhase] = Field(default_factory=list)
    total_tasks: int = 0
    parallelizable_tasks: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def count_tasks(self) -> None:
        """Update task counts."""
        self.total_tasks = sum(len(phase.tasks) for phase in self.phases)
        self.parallelizable_tasks = sum(
            1 for phase in self.phases
            for task in phase.tasks
            if task.parallelizable
        )

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Entity(BaseModel):
    """An entity in a data model."""
    name: str
    fields: Dict[str, str] = Field(default_factory=dict, description="Field name -> type")
    relationships: List[str] = Field(default_factory=list)
    validation_rules: List[str] = Field(default_factory=list)


class DataModel(BaseModel):
    """A data model document."""
    title: str
    entities: List[Entity] = Field(default_factory=list)
    notes: Optional[str] = None


class QualityCheckItem(BaseModel):
    """An item in a quality checklist."""
    description: str
    checked: bool = False
    category: str = "general"


class QualityChecklist(BaseModel):
    """A quality checklist document."""
    title: str
    items: List[QualityCheckItem] = Field(default_factory=list)
    passed: bool = False

    def calculate_passed(self) -> None:
        """Update passed status based on all items being checked."""
        self.passed = all(item.checked for item in self.items) if self.items else False


class SpecMetadata(BaseModel):
    """Metadata for a spec stored in DB."""
    spec_number: int
    feature_name: str
    spec_path: str
    has_spec: bool = False
    has_plan: bool = False
    has_tasks: bool = False
    has_checklist: bool = False
    constitution_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SpecKitProjectStatus(BaseModel):
    """Status of SpecKit integration for a project."""
    initialized: bool = False
    constitution_hash: Optional[str] = None
    constitution_version: Optional[str] = None
    spec_count: int = 0
    specs: List[SpecMetadata] = Field(default_factory=list)
