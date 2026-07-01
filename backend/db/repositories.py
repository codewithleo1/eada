import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models import User, Conversation, Message
from backend.observability.logging import get_logger

log = get_logger(__name__)


class UserRepository:
    """Database operations for the User model."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_username(self, username: str) -> User | None:
        """Find a user by their username, or None if not found."""
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Find a user by their UUID, or None if not found."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(self, username: str, hashed_password: str) -> User:
        """Create a new user and persist it."""
        user = User(username=username, hashed_password=hashed_password)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        log.info("user_created", user_id=str(user.id), username=username)
        return user


class ConversationRepository:
    """Database operations for the Conversation model."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, user_id: uuid.UUID, title: str = "New Conversation") -> Conversation:
        """Start a new conversation for a user."""
        conversation = Conversation(user_id=user_id, title=title)
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        log.info("conversation_created", conversation_id=str(conversation.id), user_id=str(user_id))
        return conversation

    async def get_by_id(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> Conversation | None:
        """Get a single conversation with its messages, scoped to the owning user.

        Always filters by user_id too — this prevents one user from
        fetching another user's conversation by guessing a UUID.
        """
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
            .options(selectinload(Conversation.messages))
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[Conversation]:
        """List all conversations for a user, most recently updated first."""
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
        )
        return list(result.scalars().all())

    async def update_title(self, conversation_id: uuid.UUID, title: str) -> None:
        """Update a conversation's title (e.g. auto-generated from first message)."""
        conversation = await self.db.get(Conversation, conversation_id)
        if conversation:
            conversation.title = title
            await self.db.commit()


class MessageRepository:
    """Database operations for the Message model."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, conversation_id: uuid.UUID, role: str, content: str) -> Message:
        """Append a message to a conversation."""
        message = Message(conversation_id=conversation_id, role=role, content=content)
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def list_for_conversation(self, conversation_id: uuid.UUID) -> list[Message]:
        """Get all messages in a conversation, oldest first (chronological order)."""
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())