import json
from backend.app.services.exercise_pool_service import ExercisePoolManager

def test_canonical_subject_keys(tmp_path):
    mgr = ExercisePoolManager(storage_dir=tmp_path)
    assert mgr.canonical_subject_key("sub_english") == "sub_english"
    assert mgr.canonical_subject_key("English") == "sub_english"
    assert mgr.canonical_subject_key("Mathematik") == "sub_math"
    assert mgr.canonical_subject_key("Physik") == "sub_physics"
    assert mgr.canonical_subject_key("Biologie") == "sub_biology"
    assert mgr.canonical_subject_key("Deutsch") == "sub_german"

def test_resolve_auto_exercise_type(tmp_path):
    mgr = ExercisePoolManager(storage_dir=tmp_path)
    assert mgr.resolve_auto_exercise_type("sub_physics") == "physics_diagram"
    assert mgr.resolve_auto_exercise_type("sub_math") == "math_problem"
    assert mgr.resolve_auto_exercise_type("sub_english") == "fill_in_the_blank"

def test_get_exercise_from_empty_pool(tmp_path):
    mgr = ExercisePoolManager(storage_dir=tmp_path)
    ex = mgr.get_exercise_from_pool("sub_math", "math_problem")
    assert ex is None

def test_get_exercise_from_pool_success(tmp_path):
    mgr = ExercisePoolManager(storage_dir=tmp_path)
    dummy_exercise = {
        "status": "success",
        "exercise_type": "math_problem",
        "title": "Gleichungen",
        "content_json": "{}",
        "tutor_speech": "Hier ist eine Rechenaufgabe!"
    }
    # Seed pool file
    pool_file = tmp_path / "pool_sub_math_math_problem.json"
    with open(pool_file, "w", encoding="utf-8") as f:
        json.dump([dummy_exercise], f)

    assert pool_file.exists()
    status_before = mgr.get_pool_status()
    assert status_before.get("sub_math_math_problem") == 1

    # Retrieve from pool
    retrieved = mgr.get_exercise_from_pool("sub_math", "math_problem")
    assert retrieved is not None
    assert retrieved["title"] == "Gleichungen"

    # Pool should now be empty
    status_after = mgr.get_pool_status()
    assert status_after.get("sub_math_math_problem") == 0
    assert mgr.get_exercise_from_pool("sub_math", "math_problem") is None

def test_get_exercise_auto_fallback(tmp_path):
    mgr = ExercisePoolManager(storage_dir=tmp_path)
    dummy_exercise = {
        "status": "success",
        "exercise_type": "math_example",
        "title": "Rechenbeispiel",
        "content_json": "{}",
        "tutor_speech": "Musterbeispiel!"
    }
    pool_file = tmp_path / "pool_sub_math_math_example.json"
    with open(pool_file, "w", encoding="utf-8") as f:
        json.dump([dummy_exercise], f)

    # When auto is requested and math_problem is empty, it finds math_example
    retrieved = mgr.get_exercise_from_pool("sub_math", "auto")
    assert retrieved is not None
    assert retrieved["exercise_type"] == "math_example"

def test_legacy_cloze_file_migration(tmp_path):
    mgr = ExercisePoolManager(storage_dir=tmp_path)
    legacy_file = tmp_path / "pool_sub_english.json"
    legacy_data = [{
        "status": "success",
        "exercise_type": "fill_in_the_blank",
        "title": "English Tenses",
        "content": {"blanks": []}
    }]
    with open(legacy_file, "w", encoding="utf-8") as f:
        json.dump(legacy_data, f)

    retrieved = mgr.get_exercise_from_pool("sub_english", "fill_in_the_blank")
    assert retrieved is not None
    assert retrieved["title"] == "English Tenses"

def test_start_stop_lifecycle(tmp_path):
    mgr = ExercisePoolManager(storage_dir=tmp_path)
    mgr.start()
    assert mgr._worker_thread is not None
    assert mgr._worker_thread.is_alive()

    # Re-starting should be idempotent
    mgr.start()

    mgr.stop()
    assert not mgr._worker_thread.is_alive()


def test_replenish_does_nothing_while_pool_disabled(tmp_path, monkeypatch):
    # Abgeschalteter Vorrat darf auch ad hoc keine Übungen (= OpenAI-Aufrufe) nachproduzieren
    monkeypatch.setattr("backend.app.config.EXERCISE_POOL_ENABLED", False)
    mgr = ExercisePoolManager(storage_dir=tmp_path)
    called = []
    monkeypatch.setattr(mgr, "_replenish_single_key", lambda *a: called.append(a))
    mgr.trigger_background_replenish("sub_math", "math_problem")
    assert called == []
    assert not mgr._wake_event.is_set()
