import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from datetime import datetime

from backend.api.deps import get_current_user, get_conversation_repo
from backend.db.repositories import ConversationRepository

router = APIRouter(prefix="/conversations", tags=["conversations"])


class MessageResponse(BaseModel):
    role: str
    content: str
    created_at: datetime


class ConversationSummary(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationSummary):
    messages: list[MessageResponse]


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    current_user: dict = Depends(get_current_user),
    conv_repo: ConversationRepository = Depends(get_conversation_repo),
) -> list[ConversationSummary]:
    """List all conversations belonging to the authenticated user."""
    user_id = uuid.UUID(current_user["sub"])
    conversations = await conv_repo.list_for_user(user_id)
    return [
        ConversationSummary(
            id=c.id, title=c.title, created_at=c.created_at, updated_at=c.updated_at
        )
        for c in conversations
    ]


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    conv_repo: ConversationRepository = Depends(get_conversation_repo),
) -> ConversationDetail:
    """Get a single conversation with its full message history."""
    user_id = uuid.UUID(current_user["sub"])
    conversation = await conv_repo.get_by_id(conversation_id, user_id)

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[
            MessageResponse(role=m.role, content=m.content, created_at=m.created_at)
            for m in conversation.messages
        ],
    )