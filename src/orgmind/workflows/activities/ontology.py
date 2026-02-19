from dataclasses import dataclass
from typing import Any

from temporalio import activity

from orgmind.api.routers import objects
from orgmind.engine.ontology_service import OntologyService
from orgmind.storage.postgres_adapter import PostgresAdapter
from orgmind.platform.config import settings

from orgmind.storage.postgres_adapter import PostgresAdapter, PostgresConfig
from orgmind.storage.repositories.object_repository import ObjectRepository
from orgmind.storage.repositories.link_repository import LinkRepository
from orgmind.storage.repositories.domain_event_repository import DomainEventRepository
from orgmind.events.nats_bus import NatsEventBus
from uuid import UUID, uuid4
from orgmind.storage.models import ObjectModel, LinkModel
from orgmind.events.publisher import EventPublisher

@dataclass
class CreateObjectInput:
    object_type_name: str
    properties: dict[str, Any]

@dataclass
class UpdateObjectInput:
    object_id: str
    properties: dict[str, Any]

@dataclass
class LinkObjectsInput:
    source_id: str
    target_id: str
    link_type_name: str
    properties: dict[str, Any] | None = None

class OntologyActivities:
    def __init__(self):
        # Initialize Infrastructure
        self.db = PostgresAdapter(PostgresConfig())
        self.event_bus = NatsEventBus(settings.NATS_URL)
        
        # Initialize Repositories
        self.object_repo = ObjectRepository()
        self.link_repo = LinkRepository()
        self.event_repo = DomainEventRepository()
        
        # Initialize Services
        self.event_publisher = EventPublisher(self.event_bus)
        
        self.service = OntologyService(
            object_repo=self.object_repo,
            link_repo=self.link_repo,
            event_repo=self.event_repo,
            event_publisher=self.event_publisher,
        )

    async def connect(self):
        """Establish connections to external services."""
        # Postgres connect is synchronous (via sqlalchemy) but good to be explicit
        self.db.connect()
        # NATS connect is async
        await self.event_bus.connect()

    @activity.defn
    async def create_object_activity(self, input: CreateObjectInput) -> str:
        activity.logger.info(f"Creating object of type {input.object_type_name}")
        tenant_id = UUID('00000000-0000-0000-0000-000000000000')

        with self.db.get_session() as session:
            obj_type = self.object_repo.get_type_by_name(session, input.object_type_name)
            if not obj_type:
                raise ValueError(f"Object type '{input.object_type_name}' not found")

            # Create ObjectModel
            obj = ObjectModel(
                id=str(uuid4()),
                type_id=obj_type.id,
                data=input.properties,
                status="active",
                version=1
            )
            
            created = await self.service.create_object(
                session=session,
                entity=obj,
                tenant_id=tenant_id,
                user_id=None
            )
            return str(created.id)

    @activity.defn
    async def update_object_activity(self, input: UpdateObjectInput) -> None:
        activity.logger.info(f"Updating object {input.object_id}")
        tenant_id = UUID('00000000-0000-0000-0000-000000000000')

        with self.db.get_session() as session:
            await self.service.update_object(
                session=session,
                object_id=input.object_id,
                updates={'data': input.properties},
                tenant_id=tenant_id,
                user_id=None
            )

    @activity.defn
    async def link_objects_activity(self, input: LinkObjectsInput) -> None:
        activity.logger.info(f"Linking {input.source_id} -> {input.target_id}")
        tenant_id = UUID('00000000-0000-0000-0000-000000000000')

        with self.db.get_session() as session:
            link_type = self.link_repo.get_type_by_name(session, input.link_type_name)
            if not link_type:
                raise ValueError(f"Link type '{input.link_type_name}' not found")

            link = LinkModel(
                id=str(uuid4()),
                type_id=link_type.id,
                source_id=input.source_id,
                target_id=input.target_id,
                data=input.properties or {}
            )

            await self.service.create_link(
                session=session,
                entity=link,
                tenant_id=tenant_id,
                user_id=None
            )
