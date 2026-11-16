from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Day = Literal['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


class Model(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, allow_inf_nan=False)


class ProfileUpdate(Model):
    name: str = Field(min_length=1, max_length=80)
    goal: str = Field(min_length=3, max_length=240)
    experience: Literal['beginner', 'intermediate', 'advanced'] = 'beginner'
    weekly_days: int = Field(ge=1, le=7)
    minutes_per_session: int = Field(ge=10, le=180)
    equipment: str = Field(max_length=240)
    dietary_preferences: str = Field(max_length=240)
    weekly_budget: float = Field(ge=0, le=10000)
    scheduled_days: list[Day] = Field(default_factory=list, max_length=7)
    food_allergies: str = Field(default='', max_length=240)
    limitations: str = Field(default='', max_length=500)
    budget_currency: Literal['USD', 'HKD'] = 'USD'

    @model_validator(mode='after')
    def valid_schedule(self):
        if len(self.scheduled_days) != len(set(self.scheduled_days)):
            raise ValueError('Scheduled days must be unique')
        if self.scheduled_days and len(self.scheduled_days) != self.weekly_days:
            raise ValueError('Select exactly weekly_days scheduled days, or leave the schedule empty')
        return self


class WorkoutLog(Model):
    exercise: str = Field(min_length=2, max_length=100)
    duration_minutes: int = Field(ge=1, le=300)
    perceived_effort: int = Field(ge=1, le=10)
    notes: str = Field(default='', max_length=500)


class Exercise(Model):
    name: str = Field(min_length=1, max_length=100)
    sets: int = Field(ge=1, le=6)
    reps: str = Field(min_length=1, max_length=40)
    rest_seconds: int = Field(default=45, ge=0, le=300)


class WorkoutDraft(Model):
    focus: str = Field(min_length=1, max_length=160)
    duration_minutes: int = Field(ge=10, le=180)
    exercises: list[Exercise] = Field(min_length=1, max_length=8)


class Workout(WorkoutDraft):
    day: Day


class Meal(Model):
    name: str = Field(min_length=1, max_length=120)
    why: str = Field(min_length=1, max_length=500)
    cost: float = Field(ge=0)
    calories: int = Field(ge=0)
    protein_g: float = Field(ge=0)
    servings_per_week: int = Field(ge=1, le=21)
    ingredients: str = Field(max_length=1000)


class PlanContent(Model):
    summary: str = Field(min_length=1, max_length=2000)
    workouts: list[Workout] = Field(min_length=1, max_length=7)
    meals: list[Meal] = Field(default_factory=list, max_length=21)
    adaptation_note: str = Field(min_length=1, max_length=2000)
    safety_note: str = Field(min_length=1, max_length=1000)
    estimated_weekly_cost: float = Field(ge=0)
    budget_currency: Literal['USD', 'HKD'] = 'USD'


class PlanSave(Model):
    title: str = Field(default='Your balanced week', min_length=1, max_length=100)
    content: PlanContent
    source: Literal['tacc_qwen', 'llm', 'local_fallback', 'mixed'] = 'local_fallback'
    workflow_id: Optional[int] = None


class PoseRange(Model):
    min: float = Field(ge=0, le=360)
    max: float = Field(ge=0, le=360)

    @model_validator(mode='after')
    def ordered(self):
        if self.max < self.min:
            raise ValueError('range_of_motion.max must be at least min')
        return self


class PoseLandmark(Model):
    x: float = Field(ge=-2, le=3)
    y: float = Field(ge=-2, le=3)
    z: float = Field(ge=-10, le=10)
    visibility: float = Field(ge=0, le=1)


class LandmarkSample(Model):
    time_seconds: float = Field(ge=0, le=18000)
    landmarks: list[PoseLandmark] = Field(min_length=33, max_length=33)


class SideCounts(Model):
    left: int = Field(ge=0, le=10000)
    right: int = Field(ge=0, le=10000)


class PoseThresholds(Model):
    bent: float = Field(gt=0, lt=180)
    extended: float = Field(gt=0, lt=180)
    calibrated: bool = False

    @model_validator(mode='after')
    def ordered(self):
        if self.bent >= self.extended:
            raise ValueError('Bent threshold must be below extended threshold')
        return self


class PoseSession(Model):
    exercise: Literal['Squat', 'Bicep curl', 'Arm circles']
    duration_seconds: float = Field(gt=0, le=18000)
    reps: int = Field(ge=0, le=10000)
    analyzed_frames: int = Field(ge=1, le=2000000)
    average_confidence: float = Field(ge=0, le=1)
    counts_by_side: Optional[SideCounts] = None
    counting_method: Optional[Literal['full_cycles_per_arm_sum', 'bilateral_full_cycles']] = None
    thresholds: Optional[PoseThresholds] = None
    range_of_motion: PoseRange
    form_cues: list[str] = Field(default_factory=list, max_length=30)
    source: Literal['webcam', 'upload']
    landmark_samples: list[LandmarkSample] = Field(default_factory=list, max_length=8)

    @model_validator(mode='after')
    def sample_timing(self):
        if self.counts_by_side and (self.exercise != 'Bicep curl' or self.reps != self.counts_by_side.left + self.counts_by_side.right):
            raise ValueError('Curl total must equal left plus right counts')
        times = [sample.time_seconds for sample in self.landmark_samples]
        if times != sorted(times) or any(t > self.duration_seconds for t in times):
            raise ValueError('Landmark samples must be chronological and within the session duration')
        return self

    @field_validator('form_cues')
    @classmethod
    def cue_lengths(cls, cues):
        if any(len(cue) > 500 for cue in cues):
            raise ValueError('Form cues must be at most 500 characters')
        return cues


class AgentRequest(Model):
    message: str = Field(default='', max_length=1200)
    pose_session_id: Optional[int] = Field(default=None, ge=1)


class ChatRequest(Model):
    message: str = Field(min_length=1, max_length=1200)
    agent_id: Optional[str] = None


class GoalDraft(Model):
    summary: str = Field(min_length=1, max_length=1000)
    priorities: list[str] = Field(min_length=1, max_length=10)


class GoalResult(GoalDraft):
    constraints: list[str] = Field(min_length=1, max_length=20)
    target_sessions: int = Field(ge=1, le=7)
    target_minutes: int = Field(ge=10, le=180)


class ExerciseResult(Model):
    summary: str
    workouts: list[Workout] = Field(min_length=1, max_length=7)


class ExerciseDraft(Model):
    summary: str
    workouts: list[WorkoutDraft] = Field(min_length=1, max_length=7)


class NutritionDraft(Model):
    menu_id: str
    summary: str = Field(min_length=1, max_length=1000)


class NutritionResult(Model):
    summary: str
    meals: list[Meal] = Field(default_factory=list, max_length=21)
    estimated_weekly_cost: float = Field(ge=0)
    budget_currency: Literal['USD', 'HKD']
    notes: list[str]


class FeedbackResult(Model):
    summary: str
    observations: list[str]
    suggestions: list[str]
    confidence_note: str
    metrics: dict[str, Any] = Field(default_factory=dict)


class EvaluationResult(Model):
    summary: str
    observations: list[str]
    recommendations: list[str]
    replan_recommended: bool
    adherence_percent: float = Field(ge=0, le=100)
    average_effort: float = Field(ge=0, le=10)
