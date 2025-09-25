from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from uuid import UUID
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from .article import Article


class Publication(SQLModel, table=True):
    __tablename__ = "publications"
    
    id: UUID = Field(
        default=None,
        primary_key=True,
        nullable=False,
        sa_column_kwargs={"server_default": "gen_random_uuid()"}
    )
    title: str = Field(max_length=255, nullable=False, index=True)
    url: str = Field(max_length=512, nullable=False)
    rss_feed_url: str = Field(max_length=512, nullable=False)
    publisher: str = Field(max_length=255, nullable=False)
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
    
    # Relationship with Article
    articles: List["Article"] = Relationship(back_populates="publication")