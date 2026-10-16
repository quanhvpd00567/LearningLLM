from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ProductInput(BaseModel):
    category_id: UUID
    name: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=32000)
    attributes: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True

    @field_validator("name", "description")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Text must not be blank")
        return value


class KnowledgeInput(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=100000)
    is_active: bool = True

    @field_validator("title", "content")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Text must not be blank")
        return value


class VariantInput(BaseModel):
    sku: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_-]+$")
    options: dict[str, Any] = Field(default_factory=dict)
    price: Decimal = Field(ge=0, max_digits=14, decimal_places=0)
    stock: int = Field(ge=0, strict=True)
