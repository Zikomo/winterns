"""Pydantic schemas for Wintern CRUD operations."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from wintern.winterns.models import DeliveryType, SourceType


# Source Config Schemas
class SourceConfigBase(BaseModel):
    """Base schema for source configuration."""

    source_type: SourceType
    config: dict = Field(default_factory=dict)
    is_active: bool = True


class SourceConfigCreate(SourceConfigBase):
    """Schema for creating a source configuration."""

    pass


class SourceConfigUpdate(BaseModel):
    """Schema for updating a source configuration."""

    source_type: SourceType | None = None
    config: dict | None = None
    is_active: bool | None = None


class SourceConfigResponse(SourceConfigBase):
    """Schema for source configuration response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    wintern_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# Delivery Config Schemas
class DeliveryConfigBase(BaseModel):
    """Base schema for delivery configuration."""

    delivery_type: DeliveryType
    config: dict = Field(default_factory=dict)
    is_active: bool = True


class DeliveryConfigCreate(DeliveryConfigBase):
    """Schema for creating a delivery configuration."""

    pass


class DeliveryConfigUpdate(BaseModel):
    """Schema for updating a delivery configuration."""

    delivery_type: DeliveryType | None = None
    config: dict | None = None
    is_active: bool | None = None


class DeliveryConfigResponse(DeliveryConfigBase):
    """Schema for delivery configuration response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    wintern_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# Wintern Schemas
class WinternBase(BaseModel):
    """Base schema for Wintern."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    context: str = Field(..., min_length=1)
    cron_schedule: str | None = None


class WinternCreate(WinternBase):
    """Schema for creating a Wintern."""

    source_configs: list[SourceConfigCreate] = Field(default_factory=list)
    delivery_configs: list[DeliveryConfigCreate] = Field(default_factory=list)


class WinternUpdate(BaseModel):
    """Schema for updating a Wintern. All fields are optional."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    context: str | None = Field(None, min_length=1)
    cron_schedule: str | None = None
    is_active: bool | None = None


class WinternResponse(WinternBase):
    """Schema for Wintern response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    is_active: bool
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime
    source_configs: list[SourceConfigResponse] = []
    delivery_configs: list[DeliveryConfigResponse] = []


class WinternListResponse(BaseModel):
    """Schema for paginated Wintern list response."""

    items: list[WinternResponse]
    total: int
    skip: int
    limit: int
