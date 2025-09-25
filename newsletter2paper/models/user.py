from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from uuid import UUID
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from .issue import Issue, UserIssue


class User(SQLModel, table=True):
    __tablename__ = "users"
    
    id: UUID = Field(
        default=None,
        primary_key=True,
        nullable=False,
        sa_column_kwargs={"server_default": "gen_random_uuid()"}
    )
    email: str = Field(
        max_length=255,
        nullable=False,
        unique=True
    )
    username: str = Field(
        max_length=255,
        nullable=False,
        unique=True
    )
    password: str = Field(
        max_length=255,
        nullable=False
    )
    first_name: str = Field(max_length=255, nullable=False)
    last_name: str = Field(max_length=255, nullable=False)
    created_at: Optional[datetime] = Field(
        default=None,
        nullable=True,
        sa_column_kwargs={"server_default": "CURRENT_TIMESTAMP"}
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        nullable=True,
        sa_column_kwargs={"server_default": "CURRENT_TIMESTAMP"}
    )
    
    # Relationship with issues through the association table
    issues: List["Issue"] = Relationship(
        back_populates="users",
        link_model="UserIssue"
    )