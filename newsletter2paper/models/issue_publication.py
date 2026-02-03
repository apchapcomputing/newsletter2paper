from datetime import datetime
from typing import Optional, TYPE_CHECKING
from uuid import UUID
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from .issue import Issue
    from .publication import Publication


class IssuePublication(SQLModel, table=True):
    """Association table for the many-to-many relationship between issues and publications"""
    __tablename__ = "issue_publications"

    issue_id: UUID = Field(foreign_key="issues.id", primary_key=True)
    publication_id: UUID = Field(foreign_key="publications.id", primary_key=True)
    remove_images: bool = Field(default=False, description="Remove images from this publication's articles in PDFs")
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
    
    # Relationships
    issue: "Issue" = Relationship(back_populates="issue_publications")
    publication: "Publication" = Relationship(back_populates="issue_publications")