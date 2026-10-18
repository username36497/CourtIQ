import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, String, Text, JSON, DateTime, ForeignKey, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

URL = os.getenv('DATABASE_URL', 'sqlite:///./courtiq.db')
engine = create_engine(URL, connect_args={'check_same_thread': False} if URL.startswith('sqlite') else {})
Session = sessionmaker(engine, expire_on_commit=False)
class Base(DeclarativeBase): pass
class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
class LoginSession(Base):
    __tablename__ = 'login_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    expires: Mapped[float]
class Build(Base):
    __tablename__ = 'builds'
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), index=True)
    name: Mapped[str] = mapped_column(String(80))
    position: Mapped[str] = mapped_column(String(2))
    height: Mapped[str] = mapped_column(String(20))
    style: Mapped[str] = mapped_column(String(300))
    attributes: Mapped[dict] = mapped_column(JSON)
class Chunk(Base):
    __tablename__ = 'chunks'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(150))
    title: Mapped[str] = mapped_column(String(200))
    edition: Mapped[str] = mapped_column(String(20))
    patch: Mapped[str] = mapped_column(String(60))
    url: Mapped[str] = mapped_column(String(1000))
    sample: Mapped[bool]
    text: Mapped[str] = mapped_column(Text)
class Chat(Base):
    __tablename__ = 'chats'
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
class Run(Base):
    __tablename__ = 'pipeline_runs'
    id: Mapped[int] = mapped_column(primary_key=True)
    summary: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
def init_db():
    Base.metadata.create_all(engine)
    # Small explicit migration from v1. Unowned legacy rows are retained but
    # never exposed to newly created users. Back up the DB before upgrading.
    for table in ('builds','chats'):
        if 'owner_id' not in {c['name'] for c in inspect(engine).get_columns(table)}:
            with engine.begin() as conn:
                conn.execute(text(f'ALTER TABLE {table} ADD COLUMN owner_id INTEGER REFERENCES users(id)'))
