
import uuid
from datetime import date, datetime

from sqlalchemy import (
    DateTime,
    Integer,
    Text,
    UniqueConstraint,
    text,
    BigInteger
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgvector.sqlalchemy import VECTOR

class Base(DeclarativeBase):
    pass


class DocumentChunks(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_key", "chunk_index", name="document_chunks_document_key_chunk_index_key"),
    )

    id: Mapped[int] = mapped_column(
            BigInteger,
            primary_key=True,
            autoincrement=True,
    )
    document_key: Mapped[str] = mapped_column(Text, nullable=False)
    page_num: Mapped[int] = mapped_column(Integer, nullable=True)
    chapter: Mapped[str] = mapped_column(Text, nullable=True)
    section: Mapped[str] = mapped_column(Text, nullable=True)
    subsection: Mapped[str] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata",JSONB, default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False) 
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embeddings: Mapped[list[float]] = mapped_column(VECTOR(1024), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)