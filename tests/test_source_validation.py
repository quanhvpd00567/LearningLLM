from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.sources import KnowledgeInput, ProductInput, VariantInput


@pytest.mark.parametrize("values", [
    {"price": -1, "stock": 1}, {"price": 100, "stock": -1},
    {"price": "1.5", "stock": 1}, {"price": 100, "stock": 1.5},
])
def test_invalid_commerce_values(values):
    with pytest.raises(ValidationError):
        VariantInput(sku="DEMO-42", **values)


def test_blank_source_content_rejected():
    with pytest.raises(ValidationError):
        KnowledgeInput(title="FAQ", content="  ")
    with pytest.raises(ValidationError):
        ProductInput(category_id=uuid4(), name=" ", description="Giày")
