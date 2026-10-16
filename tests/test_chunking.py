import pytest

from app.chatbot.rag.chunking import chunk_text


def test_short_and_empty_documents():
    assert chunk_text("\n  ") == []
    assert chunk_text("  Giày   đi bộ.\n\n  Đế  êm. ") == ["Giày đi bộ.\n\nĐế êm."]


def test_chunking_preserves_long_unbroken_text_and_is_bounded():
    text = "a" * 10000
    chunks = chunk_text(text, max_chars=100, overlap=10)
    assert all(0 < len(c) <= 100 for c in chunks)
    assert sum(len(c) for c in chunks) - 10 * (len(chunks) - 1) == len(text)
    assert chunks == chunk_text(text, max_chars=100, overlap=10)


def test_tail_is_preserved_for_vietnamese_text():
    text = "Chính sách đổi trả sản phẩm. " * 300 + "KẾT THÚC"
    chunks = chunk_text(text)
    assert len(chunks) > 1
    assert chunks[-1].endswith("KẾT THÚC")
    assert all(len(c) <= 1400 for c in chunks)


@pytest.mark.parametrize("size,overlap", [(0,0),(10,10),(10,-1),(10,11)])
def test_invalid_chunk_options(size, overlap):
    with pytest.raises(ValueError):
        chunk_text("text", size, overlap)
