from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

Budget = Literal["low", "medium", "high"]
FallbackReason = Literal["no_api_key", "rate_limited", "llm_error", "invalid_output"]

MAX_ADDITIONAL_PREFERENCES = 500


class RecommendationRequest(BaseModel):
    location: str = Field(min_length=1, max_length=100)
    budget: Budget
    cuisine: Optional[str] = Field(default=None, max_length=100)
    min_rating: float = Field(default=0.0, ge=0, le=5)
    additional_preferences: str = Field(default="", max_length=MAX_ADDITIONAL_PREFERENCES)

    @field_validator("location")
    @classmethod
    def _location_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("location must not be blank")
        return value

    @field_validator("cuisine")
    @classmethod
    def _blank_cuisine_is_none(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip() or None


class RecommendationItem(BaseModel):
    rank: int
    restaurant_id: str
    name: str
    cuisine: Optional[str] = None
    rating: Optional[float] = None
    estimated_cost: Optional[int] = None
    explanation: Optional[str] = None
    neighborhood: Optional[str] = None
    rest_type: Optional[str] = None


class RecommendationMeta(BaseModel):
    candidates_considered: int
    used_llm: bool = False
    fallback: bool = False
    budget_relaxed: bool = False
    fallback_reason: Optional[FallbackReason] = None
    retry_after_seconds: Optional[int] = None
    cached: bool = False


class RecommendationResponse(BaseModel):
    summary: Optional[str] = None
    recommendations: List[RecommendationItem]
    meta: RecommendationMeta


class MetaResponse(BaseModel):
    neighborhoods: List[str]
    cuisines: List[str]
