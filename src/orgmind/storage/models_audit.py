import datetime
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from orgmind.storage.models import Base

class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    
    # User who performed the action (nullable for system actions or unauthenticated attempts)
    user_id: Mapped[str | None] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    
    action: Mapped[str] = mapped_column(String, nullable=False)  # e.g., "object.read"
    resource: Mapped[str] = mapped_column(String, nullable=False) # e.g., "object:task:123"
    decision: Mapped[str] = mapped_column(String, nullable=False) # "allow" or "deny"
    reason: Mapped[str | None] = mapped_column(Text, nullable=True) # e.g., "Policy p1 matched"
    
    metadata_context: Mapped[dict | None] = mapped_column(JSON, nullable=True) # Extra info (IP, UA)

    # Relationships
    user = relationship("UserModel")
