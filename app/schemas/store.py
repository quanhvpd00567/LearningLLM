from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class CartUpdate(BaseModel):
    model_config = {"extra": "forbid"}
    quantity: int = Field(ge=0, le=20, strict=True)


class CheckoutInput(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}
    customer_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=8, max_length=20, pattern=r"^[+0-9 ()-]+$")
    address: str = Field(min_length=10, max_length=500)
    note: str = Field(default="", max_length=500)
    idempotency_key: UUID


class StoreMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class StoreChatInput(BaseModel):
    model_config = {"extra": "forbid"}
    messages: list[StoreMessage] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def bounded_history(self):
        if self.messages[-1].role != "user" or sum(len(m.content) for m in self.messages) > 16000:
            raise ValueError("End with a user message; history must be <= 16000 characters")
        return self
