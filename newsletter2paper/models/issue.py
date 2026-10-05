from datetime import datetime
from typing import Optional, List, TYPE_CHECKING, ForwardRef
from uuid import UUID
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from .issue_publication import IssuePublication
else:
    IssuePublication = ForwardRef("IssuePublication")


class UserIssue(SQLModel, table=True):
    """Association table for the many-to-many relationship between users and issues"""
    __tablename__ = "user_issues"

    # References auth.users(id) in the database (Supabase Auth owns identity); the foreign key
    # is declared in SQL because SQLModel metadata cannot see the auth schema.
    user_id: UUID = Field(primary_key=True)
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
    custom_start_date: Optional[datetime] = Field(
        default=None,
        nullable=True
    )
    custom_end_date: Optional[datetime] = Field(
        default=None,
        nullable=True
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
    
    # Relationship with publications through the association table
    issue_publications: List["IssuePublication"] = Relationship(back_populates="issue")