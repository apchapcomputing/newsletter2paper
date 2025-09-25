from datetime import datetime
from typing import Optional, TYPE_CHECKING
from uuid import UUID
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from .publication import Publication


class Article(SQLModel, table=True):
    __tablename__ = "articles"
    
    id: UUID = Field(
        default=None,
        primary_key=True,
        nullable=False,
        sa_column_kwargs={"server_default": "gen_random_uuid()"}
    )
    title: str = Field(max_length=255, nullable=False)
    subtitle: Optional[str] = Field(default=None, max_length=255, nullable=True)
    date_published: datetime = Field(nullable=False)
    author: str = Field(max_length=255, nullable=False)
    publication_id: Optional[UUID] = Field(default=None, foreign_key="publications.id", nullable=True)
    content_url: str = Field(max_length=512, nullable=False)
    storage_url: Optional[str] = Field(default=None, max_length=512, nullable=True)
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
    
    # Relationship
    publication: Optional["Publication"] = Relationship(back_populates="articles")