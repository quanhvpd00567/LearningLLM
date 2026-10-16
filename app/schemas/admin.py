from pydantic import BaseModel, Field, field_validator

from app.schemas.sources import KnowledgeInput, ProductInput, VariantInput


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class ProductWrite(ProductInput):
    variants: list[VariantInput] = Field(default_factory=list, max_length=50)
    expected_version: int | None = Field(default=None, ge=1)

    @field_validator("variants")
    @classmethod
    def unique_skus(cls, values):
        if len({v.sku for v in values}) != len(values):
            raise ValueError("SKU must not repeat")
        return values


class KnowledgeWrite(KnowledgeInput):
    expected_version: int | None = Field(default=None, ge=1)


class CategoryInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError("Name must not be blank")
        return value.strip()


class SiteSettingsInput(BaseModel):
    model_config = {"extra": "forbid"}
    shop_name: str = Field(min_length=1, max_length=120)
    contact_email: str = Field(default="", max_length=254, pattern=r"^$|^[^\s@]+@[^\s@]+\.[^\s@]+$")
    low_stock_threshold: int = Field(default=5, ge=0, le=10000)
    embedding_paused: bool = False

    @field_validator("shop_name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError("Name must not be blank")
        return value.strip()
