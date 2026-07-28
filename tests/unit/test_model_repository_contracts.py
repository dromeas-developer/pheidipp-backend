import inspect

from app.models.activity import Activity
from app.repositories.coaching_message_repository import CoachingMessageRepository
from app.repositories.system_event_repository import SystemEventRepository
from app.repositories.twin_state_repository import TwinStateRepository


def _public_async_methods(cls: type) -> set[str]:
    return {
        name
        for name, obj in cls.__dict__.items()
        if not name.startswith("_") and inspect.iscoroutinefunction(obj)
    }


def _public_method_names(cls: type) -> set[str]:
    return {
        name
        for name, obj in cls.__dict__.items()
        if not name.startswith("_")
        and (inspect.isfunction(obj) or inspect.iscoroutinefunction(obj))
    }


class TestActivityModelColumns:
    def test_no_avg_hr_or_summary_columns(self):
        columns = {c.name for c in Activity.__table__.columns}
        forbidden = {"avg_hr", "avg_pace", "avg_power", "avg_cadence"}
        found = forbidden & columns
        assert not found, f"Forbidden columns found: {found}"

    def test_no_lap_data_columns(self):
        columns = {c.name for c in Activity.__table__.columns}
        lap_like = {c for c in columns if "lap" in c.lower()}
        assert not lap_like, f"Lap-data columns found: {lap_like}"


class TestTwinStateRepositoryContract:
    def test_exposes_exactly_six_methods(self):
        methods = _public_async_methods(TwinStateRepository)
        assert len(methods) == 6, f"Expected 6 methods, got {len(methods)}: {methods}"

    def test_exposes_insert_get_latest_get_by_id_get_by_activity_get_by_activity_and_trigger_get_history(
        self,
    ):
        methods = _public_async_methods(TwinStateRepository)
        expected = {
            "insert",
            "get_latest",
            "get_by_id",
            "get_by_activity",
            "get_by_activity_and_trigger",
            "get_history",
        }
        assert methods == expected, f"Expected {expected}, got {methods}"

    def test_no_update_delete_or_mutation_methods(self):
        mutation_prefixes = ("update", "delete", "save", "merge", "upsert")
        names = _public_async_methods(TwinStateRepository)
        mutation = {n for n in names if any(n.startswith(p) for p in mutation_prefixes)}
        assert not mutation, f"Mutation methods found: {mutation}"


class TestCoachingMessageRepositoryContract:
    def test_exposes_exactly_six_coaching_message_methods(self):
        methods = _public_async_methods(CoachingMessageRepository)
        assert len(methods) == 6, f"Expected 6 methods, got {len(methods)}: {methods}"

    def test_coaching_message_exposes_insert_get_by_athlete_id_get_by_athlete_and_type_get_existing_first_message_get_by_activity_and_type_get_all_count(
        self,
    ):
        methods = _public_async_methods(CoachingMessageRepository)
        expected = {
            "insert",
            "get_by_athlete_id",
            "get_by_athlete_and_type",
            "get_existing_first_message",
            "get_by_activity_and_type",
            "get_all_count",
        }
        assert methods == expected, f"Expected {expected}, got {methods}"

    def test_coaching_message_no_update_delete_or_mutation_methods(self):
        mutation_prefixes = ("update", "delete", "save", "merge", "upsert")
        names = _public_async_methods(CoachingMessageRepository)
        mutation = {n for n in names if any(n.startswith(p) for p in mutation_prefixes)}
        assert not mutation, f"Mutation methods found: {mutation}"


class TestSystemEventRepositoryContract:
    def test_exposes_only_add_method(self):
        methods = _public_async_methods(SystemEventRepository)
        assert methods == {"add"}, f"Expected {{'add'}}, got {methods}"

    def test_no_read_update_or_delete_methods(self):
        names = _public_method_names(SystemEventRepository)
        forbidden_patterns = {
            "update",
            "delete",
            "save",
            "merge",
            "get",
            "list",
            "find",
            "query",
        }
        suspicious = {
            n for n in names if any(p in n.lower() for p in forbidden_patterns)
        }
        assert not suspicious, f"Forbidden method patterns found: {suspicious}"

    def test_method_count_is_exactly_one(self):
        methods = _public_async_methods(SystemEventRepository)
        assert len(methods) == 1, f"Expected 1 method, got {len(methods)}: {methods}"
