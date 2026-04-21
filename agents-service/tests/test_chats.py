import pytest
from sqlalchemy import create_engine

from obllomov.schemas.domain.entries import ScenePlan
from obllomov.schemas.domain.raw import RawScenePlan
from obllomov.schemas.orm.chat import Base
from obllomov.services.chat import ChatService
from obllomov.services.events import ChatEventCallback, StageEvent
from obllomov.storage.db.repository import SessionRepository


@pytest.fixture
def engine():
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    return e


@pytest.fixture
def repo(engine):
    return SessionRepository(engine)


@pytest.fixture
def chat(repo):
    return ChatService(repo)


def _make_event(stage="floor", completed=1, total=8):
    return StageEvent(
        stage=stage,
        completed=completed,
        total=total,
        scene_plan=ScenePlan(query="test query"),
        raw_scene_plan=RawScenePlan(),
    )


class TestSessionRepository:
    def test_create_session(self, repo):
        session = repo.create_session("user-1")
        assert session.user_id == "user-1"
        assert session.id is not None

    def test_get_session(self, repo):
        created = repo.create_session("user-1")
        fetched = repo.get_session(created.id)
        assert fetched is not None
        assert fetched.id == created.id

    def test_get_session_not_found(self, repo):
        assert repo.get_session("nonexistent") is None

    def test_list_sessions(self, repo):
        repo.create_session("user-1")
        repo.create_session("user-1")
        repo.create_session("user-2")
        assert len(repo.list_sessions("user-1")) == 2
        assert len(repo.list_sessions("user-2")) == 1

    def test_add_interaction_increments_sequence(self, repo):
        session = repo.create_session("user-1")
        i1 = repo.add_interaction(session.id, "query 1")
        i2 = repo.add_interaction(session.id, "query 2")
        assert i1.sequence == 1
        assert i2.sequence == 2

    def test_get_interaction(self, repo):
        session = repo.create_session("user-1")
        repo.add_interaction(session.id, "q1")
        repo.add_interaction(session.id, "q2")
        fetched = repo.get_interaction(session.id, 2)
        assert fetched is not None
        assert fetched.query == "q2"

    def test_get_interaction_not_found(self, repo):
        session = repo.create_session("user-1")
        assert repo.get_interaction(session.id, 99) is None

    def test_add_stage(self, repo):
        session = repo.create_session("user-1")
        interaction = repo.add_interaction(session.id, "q1")
        stage = repo.add_stage(interaction.id, "floor", {"rooms": []}, {"raw": True})
        assert stage.stage_name == "floor"
        assert stage.scene_plan == {"rooms": []}
        assert stage.raw_scene_plan == {"raw": True}

    def test_get_last_stage(self, repo):
        session = repo.create_session("user-1")
        interaction = repo.add_interaction(session.id, "q1")
        repo.add_stage(interaction.id, "floor", {"step": 1}, {})
        repo.add_stage(interaction.id, "walls", {"step": 2}, {})
        last = repo.get_last_stage(session.id)
        assert last is not None
        assert last.stage_name == "walls"

    def test_get_last_stage_empty(self, repo):
        session = repo.create_session("user-1")
        assert repo.get_last_stage(session.id) is None

    def test_session_contains_interactions_and_stages(self, repo):
        session = repo.create_session("user-1")
        i1 = repo.add_interaction(session.id, "q1")
        repo.add_stage(i1.id, "floor", {}, {})
        repo.add_stage(i1.id, "walls", {}, {})

        fetched = repo.get_session(session.id)
        assert len(fetched.interactions) == 1
        assert len(fetched.interactions[0].stages) == 2


class TestChatService:
    def test_start_session(self, chat):
        session = chat.start_session("user-1")
        assert session.user_id == "user-1"

    def test_start_interaction(self, chat):
        session = chat.start_session("user-1")
        interaction = chat.start_interaction(session.id, "design a room")
        assert interaction.query == "design a room"
        assert interaction.sequence == 1

    def test_save_stage(self, chat):
        session = chat.start_session("user-1")
        interaction = chat.start_interaction(session.id, "q")
        scene_plan = ScenePlan(query="test")
        raw = RawScenePlan()

        stage = chat.save_stage(interaction.id, "floor", scene_plan, raw)
        assert stage.stage_name == "floor"
        assert isinstance(stage.scene_plan, dict)

    def test_get_last_scene_json(self, chat):
        session = chat.start_session("user-1")
        interaction = chat.start_interaction(session.id, "q")
        scene = ScenePlan(query="test")
        raw = RawScenePlan()
        chat.save_stage(interaction.id, "floor", scene, raw)
        chat.save_stage(interaction.id, "walls", scene, raw)

        last = chat.get_last_scene_json(session.id)
        assert last is not None

    def test_get_last_scene_json_empty(self, chat):
        session = chat.start_session("user-1")
        assert chat.get_last_scene_json(session.id) is None

    def test_rollback(self, chat):
        session = chat.start_session("user-1")
        i1 = chat.start_interaction(session.id, "q1")
        scene = ScenePlan(query="v1")
        raw = RawScenePlan()
        chat.save_stage(i1.id, "floor", scene, raw)

        i2 = chat.start_interaction(session.id, "q2")
        scene2 = ScenePlan(query="v2")
        chat.save_stage(i2.id, "floor", scene2, raw)

        rollback = chat.rollback(session.id, to_sequence=1)
        assert rollback.query == "rollback to #1"
        assert rollback.stages[0].stage_name == "rollback"

    def test_rollback_not_found(self, chat):
        session = chat.start_session("user-1")
        with pytest.raises(ValueError, match="not found"):
            chat.rollback(session.id, to_sequence=99)

    def test_rollback_no_stages(self, chat):
        session = chat.start_session("user-1")
        chat.start_interaction(session.id, "q1")
        with pytest.raises(ValueError, match="has no stages"):
            chat.rollback(session.id, to_sequence=1)


class TestChatEventCallbackIntegration:
    def test_on_stage_persists_to_db(self, chat):
        session = chat.start_session("user-1")
        interaction = chat.start_interaction(session.id, "q")
        cb = ChatEventCallback(chat, interaction.id)

        cb.on_stage(_make_event("floor", 1, 8))
        cb.on_stage(_make_event("walls", 2, 8))

        last = chat.get_last_scene_json(session.id)
        assert last is not None

    def test_on_complete_persists_completed(self, chat):
        session = chat.start_session("user-1")
        interaction = chat.start_interaction(session.id, "q")
        cb = ChatEventCallback(chat, interaction.id)

        cb.on_stage(_make_event("floor", 1, 8))
        cb.on_complete(_make_event("completed", 8, 8))

        fetched = chat.get_session(session.id)
        stages = fetched.interactions[0].stages
        assert len(stages) == 2
        assert stages[-1].stage_name == "completed"

    def test_full_pipeline_stages(self, chat):
        session = chat.start_session("user-1")
        interaction = chat.start_interaction(session.id, "design a living room")
        cb = ChatEventCallback(chat, interaction.id)

        stage_names = ["floor", "walls", "doors", "windows",
                       "object_selection", "floor_objects", "wall_objects", "small_objects"]
        for i, name in enumerate(stage_names, 1):
            cb.on_stage(_make_event(name, i, len(stage_names)))

        cb.on_complete(_make_event("completed", len(stage_names), len(stage_names)))

        fetched = chat.get_session(session.id)
        stages = fetched.interactions[0].stages
        assert len(stages) == len(stage_names) + 1
        assert [s.stage_name for s in stages] == stage_names + ["completed"]
