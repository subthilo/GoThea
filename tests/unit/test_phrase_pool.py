import pytest
from backend.app.services.phrase_pool_service import PhrasePoolManager

def test_phrase_pool_manager_basic(tmp_path):
    mgr = PhrasePoolManager(storage_dir=tmp_path)
    # Get random phrase from error_interjections
    p1 = mgr.get_phrase("error_interjections")
    assert "text" in p1
    assert "category" in p1
    assert p1["category"] == "error_interjections"

    # Verify no repeat within 2 turns
    p2 = mgr.get_phrase("error_interjections")
    assert p2["text"] != p1["text"]

    p3 = mgr.get_phrase("error_interjections")
    assert p3["text"] != p2["text"]

def test_phrase_pool_unknown_category(tmp_path):
    mgr = PhrasePoolManager(storage_dir=tmp_path)
    p = mgr.get_phrase("non_existent_category")
    assert "text" in p
    assert p["text"] == "Sehr gut!"
