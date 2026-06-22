"""
ThroneChat — Database Models (SQLAlchemy Async ORM + SQLite)
All game state is stored here: users, castles, alliances, battles, conspiracies.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
    select,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship

from config.config import DATABASE_URL


# ═══════════════════════════════════════
# Engine & Session Factory
# ═══════════════════════════════════════

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# ═══════════════════════════════════════
# 👤 User Model
# ═══════════════════════════════════════

class User(Base):
    __tablename__ = "users"

    user_id: int = Column(BigInteger, primary_key=True)           # Telegram User ID
    username: Optional[str] = Column(String, nullable=True)        # @nickname
    first_name: str = Column(String, nullable=False, default="Лорд")
    role: str = Column(String, nullable=False, default="lord")     # 'lord' | 'king'
    army_size: int = Column(Integer, nullable=False, default=100)
    alliance_id: Optional[int] = Column(
        Integer, ForeignKey("alliances.alliance_id"), nullable=True
    )
    activity_count: int = Column(Integer, nullable=False, default=0)
    muted_until: Optional[datetime] = Column(DateTime, nullable=True)
    created_at: datetime = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_active: datetime = Column(DateTime, nullable=False, default=datetime.utcnow)
    king_opinion: str = Column(String, nullable=False, default="neutral")  # 'good' | 'bad' | 'neutral'
    authority: int = Column(Integer, nullable=False, default=50)           # King's authority points
    king_tribute_rate: float = Column(Float, nullable=False, default=0.0)  # Percentage taken by King (0.0 to 0.5)

    # Relationships
    castles = relationship(
        "Castle", back_populates="owner", foreign_keys="Castle.owner_id"
    )
    alliance = relationship(
        "Alliance", back_populates="members", foreign_keys=[alliance_id]
    )

    def __repr__(self) -> str:
        return f"<User {self.user_id} @{self.username} role={self.role}>"


# ═══════════════════════════════════════
# 🏰 Castle Model
# ═══════════════════════════════════════

class Castle(Base):
    __tablename__ = "castles"

    castle_id: int = Column(Integer, primary_key=True, autoincrement=True)
    name: str = Column(String, unique=True, nullable=False)
    owner_id: Optional[int] = Column(
        BigInteger, ForeignKey("users.user_id"), nullable=True
    )
    garrison: int = Column(Integer, nullable=False, default=0)
    army_per_hour: int = Column(Integer, nullable=False, default=10)

    owner = relationship(
        "User", back_populates="castles", foreign_keys=[owner_id]
    )

    def __repr__(self) -> str:
        return f"<Castle {self.castle_id} '{self.name}' owner={self.owner_id}>"


# ═══════════════════════════════════════
# 🤝 Alliance Model
# ═══════════════════════════════════════

class Alliance(Base):
    __tablename__ = "alliances"

    alliance_id: int = Column(Integer, primary_key=True, autoincrement=True)
    name: str = Column(String, unique=True, nullable=False)
    leader_id: int = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    created_at: datetime = Column(DateTime, nullable=False, default=datetime.utcnow)

    members = relationship(
        "User", back_populates="alliance", foreign_keys="User.alliance_id"
    )

    def __repr__(self) -> str:
        return f"<Alliance {self.alliance_id} '{self.name}'>"


# ═══════════════════════════════════════
# ⚔️ Battle Model
# ═══════════════════════════════════════

class Battle(Base):
    __tablename__ = "battles"

    battle_id: int = Column(Integer, primary_key=True, autoincrement=True)
    attacker_id: int = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    defender_id: int = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    castle_id: int = Column(Integer, ForeignKey("castles.castle_id"), nullable=False)
    attacker_army: int = Column(Integer, nullable=False)
    status: str = Column(String, nullable=False, default="pending")  # 'pending' | 'done'
    winner_id: Optional[int] = Column(BigInteger, nullable=True)
    attacker_losses: Optional[int] = Column(Integer, nullable=True)
    defender_losses: Optional[int] = Column(Integer, nullable=True)
    message_id: Optional[int] = Column(BigInteger, nullable=True)  # Live message in chat
    started_at: datetime = Column(DateTime, nullable=False, default=datetime.utcnow)
    resolved_at: Optional[datetime] = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Battle {self.battle_id} {self.attacker_id} vs {self.defender_id} status={self.status}>"


# ═══════════════════════════════════════
# 🗡️ Conspiracy Model
# ═══════════════════════════════════════

class Conspiracy(Base):
    __tablename__ = "conspiracies"

    conspiracy_id: int = Column(Integer, primary_key=True, autoincrement=True)
    chat_id: int = Column(BigInteger, nullable=False)
    initiator_id: int = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    status: str = Column(String, nullable=False, default="active")  # 'active' | 'won' | 'failed'
    rebels: dict = Column(JSON, nullable=False, default=dict)       # {str(user_id): army_committed}
    loyalists: dict = Column(JSON, nullable=False, default=dict)    # {str(user_id): army_committed}
    message_id: Optional[int] = Column(BigInteger, nullable=True)   # Live message in chat
    expires_at: datetime = Column(DateTime, nullable=False)
    created_at: datetime = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Conspiracy {self.conspiracy_id} status={self.status}>"


class ScoutReport(Base):
    __tablename__ = "scout_reports"

    report_id: int = Column(Integer, primary_key=True, autoincrement=True)
    user_id: int = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    castle_id: int = Column(Integer, ForeignKey("castles.castle_id"), nullable=False)
    garrison: int = Column(Integer, nullable=False)
    timestamp: datetime = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ScoutReport user={self.user_id} castle={self.castle_id} garrison={self.garrison}>"

# ═══════════════════════════════════════
# 🔧 Database Initialization
# ═══════════════════════════════════════

async def init_db() -> None:
    """Create all tables and seed castles if the castles table is empty."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# ═══════════════════════════════════════
# 🔍 Common Query Helpers
# ═══════════════════════════════════════

async def get_user(session: AsyncSession, user_id: int) -> Optional[User]:
    """Get a user by Telegram user_id."""
    return await session.get(User, user_id)


async def get_or_create_user(
    session: AsyncSession,
    user_id: int,
    username: Optional[str] = None,
    first_name: str = "Лорд",
) -> tuple[User, bool]:
    """Get existing user or create a new one. Returns (user, created)."""
    user = await session.get(User, user_id)
    if user:
        # Update dynamic fields
        if username:
            user.username = username
        user.first_name = first_name
        user.last_active = datetime.utcnow()
        await session.commit()
        return user, False

    user = User(
        user_id=user_id,
        username=username,
        first_name=first_name,
    )
    session.add(user)
    await session.commit()
    return user, True


async def get_king(session: AsyncSession) -> Optional[User]:
    """Get the current King, if any."""
    result = await session.execute(
        select(User).where(User.role == "king")
    )
    return result.scalar_one_or_none()


async def get_user_castles(session: AsyncSession, user_id: int) -> list[Castle]:
    """Get all castles owned by a user."""
    result = await session.execute(
        select(Castle).where(Castle.owner_id == user_id)
    )
    return list(result.scalars().all())


async def count_user_castles(session: AsyncSession, user_id: int) -> int:
    """Count castles owned by a user."""
    result = await session.execute(
        select(func.count(Castle.castle_id)).where(Castle.owner_id == user_id)
    )
    return result.scalar() or 0


async def get_army_cap(session: AsyncSession, user_id: int) -> int:
    """Calculate army cap: BASE_CAP + (castle_count × PER_CASTLE_CAP)."""
    from config.config import BASE_ARMY_CAP, CASTLE_ARMY_CAP
    count = await count_user_castles(session, user_id)
    return BASE_ARMY_CAP + (count * CASTLE_ARMY_CAP)


async def get_all_castles(session: AsyncSession) -> list[Castle]:
    """Get all castles in the game."""
    result = await session.execute(select(Castle))
    return list(result.scalars().all())


async def get_active_conspiracy(
    session: AsyncSession, chat_id: int
) -> Optional[Conspiracy]:
    """Get the currently active conspiracy for a chat, if any."""
    result = await session.execute(
        select(Conspiracy).where(
            Conspiracy.chat_id == chat_id,
            Conspiracy.status == "active",
        )
    )
    return result.scalar_one_or_none()


async def get_active_battle_for_user(
    session: AsyncSession, user_id: int
) -> Optional[Battle]:
    """Check if a user has an active (pending) battle as attacker."""
    result = await session.execute(
        select(Battle).where(
            Battle.attacker_id == user_id,
            Battle.status == "pending",
        )
    )
    return result.scalar_one_or_none()
