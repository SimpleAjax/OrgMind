import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from orgmind.storage.models import Base, ObjectModel, ObjectTypeModel, LinkModel, LinkTypeModel, EventModel, SourceModel
from orgmind.storage.repositories.object_repository import ObjectRepository
from orgmind.storage.repositories.link_repository import LinkRepository
from orgmind.storage.repositories.event_repository import EventRepository

# Use in-memory SQLite for comprehensive unit testing without external DB
@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_object_repository(session):
    repo = ObjectRepository()
    
    # Create Type
    ot = ObjectTypeModel(
        id="ot_person",
        name="Person",
        description="A human being",
        properties={"name": {"type": "string"}, "age": {"type": "integer"}}
    )
    repo.create_type(session, ot)
    
    fetched_type = repo.get_type(session, "ot_person")
    assert fetched_type.name == "Person"
    assert fetched_type.properties["name"]["type"] == "string"

    # Create Instance
    obj = ObjectModel(
        id="obj_person_001",
        type_id="ot_person",
        data={"name": "Alice", "age": 30},
        created_by="system"
    )
    repo.create(session, obj)
    
    fetched_obj = repo.get(session, "obj_person_001")
    assert fetched_obj.data["name"] == "Alice"
    assert fetched_obj.status == "active"
    
    # Update
    repo.update(session, "obj_person_001", {"data": {"age": 31}})
    updated_obj = repo.get(session, "obj_person_001")
    assert updated_obj.data["age"] == 31
    assert updated_obj.version == 2
    
def test_link_repository(session):
    obj_repo = ObjectRepository()
    link_repo = LinkRepository()
    
    # Setup Objects
    obj_repo.create_type(session, ObjectTypeModel(id="ot_node", name="Node", properties={}))
    obj_repo.create(session, ObjectModel(id="source_01", type_id="ot_node", data={}))
    obj_repo.create(session, ObjectModel(id="target_01", type_id="ot_node", data={}))
    
    # Create Link Type
    lt = LinkTypeModel(
        id="lt_connects", 
        name="connects", 
        source_type="ot_node", 
        target_type="ot_node"
    )
    link_repo.create_type(session, lt)
    
    # Create Link
    link = LinkModel(
        id="link_001",
        type_id="lt_connects",
        source_id="source_01",
        target_id="target_01",
        data={"weight": 10}
    )
    link_repo.create(session, link)
    
    # Fetch
    fetched = link_repo.get(session, "link_001")
    assert fetched.source_id == "source_01"
    assert fetched.data["weight"] == 10
    
    # Get Related
    related = link_repo.get_related(session, "source_01")
    assert len(related) == 1
    assert related[0].target_id == "target_01"

def test_event_repository(session):
    repo = EventRepository()
    
    # Create Source
    src = SourceModel(
        id="src_webhook",
        name="Webhook Source",
        provider="manual",
        config={"endpoint": "/foo"}
    )
    repo.create_source(session, src)
    
    # Create Event
    evt = EventModel(
        id="evt_001",
        source_id="src_webhook",
        event_type="test_event",
        raw_payload={"foo": "bar"}
    )
    repo.create(session, evt)
    
    fetched = repo.get(session, "evt_001")
    assert fetched.status == "received"
    assert fetched.raw_payload["foo"] == "bar"
