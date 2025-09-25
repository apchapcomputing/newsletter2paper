from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from uuid import UUID
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from .user import User


class UserIssue(SQLModel, table=True):
    """Association table for the many-to-many relationship between users and issues"""
    __tablename__ = "user_issues"

    user_id: UUID = Field(foreign_key="users.id", primary_key=True)
    issue_id: UUID = Field(foreign_key="issues.id", primary_key=True)
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


class Issue(SQLModel, table=True):
    __tablename__ = "issues"
    
    id: UUID = Field(
        default=None,
        primary_key=True,
        nullable=False,
        sa_column_kwargs={"server_default": "gen_random_uuid()"}
    )
    format: str = Field(
        max_length=50,
        nullable=False,
        sa_column_kwargs={
            "check": "format IN ('newspaper', 'essay')"
        }
    )
    target_email: Optional[str] = Field(
        default=None,
        max_length=255,
        nullable=True
    )
    frequency: str = Field(
        max_length=50,
        nullable=False
    )
    title: Optional[str] = Field(
        default=None,
        nullable=True,
        sa_type="text"
    )
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
    
    # Relationship with users through the association table
    users: List["User"] = Relationship(
        back_populates="issues",
        link_model=UserIssue
    )