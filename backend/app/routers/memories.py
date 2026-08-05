"""Memories router — user-persisted context from LLM conversations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.models.user import User
from app.schemas.memory import ClearAllResponse, MemoryCreate, MemoryListResponse, MemoryOut
from app.services.memory_service import (
    MemoryAlreadyExistsError,
    clear_all_memories,
    create_memory,
    delete_memory,
    get_user_memories,
)

router = APIRouter(prefix="/api/memories", tags=["memories"])


@router.get("", response_model=MemoryListResponse)
@limiter.limit("60/minute")
async def list_memories(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    memories = await get_user_memories(db, current_user.id)
    return MemoryListResponse(memories=[MemoryOut.model_validate(m) for m in memories])


@router.post("", response_model=MemoryOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def add_memory(
    request: Request,
    data: MemoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        memory = await create_memory(db, current_user.id, data.content)
    except MemoryAlreadyExistsError:
        raise HTTPException(status_code=409, detail="memory_already_exists") from None
    return MemoryOut.model_validate(memory)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def delete_one_memory(
    request: Request,
    memory_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_memory(db, memory_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")


@router.delete("", response_model=ClearAllResponse)
@limiter.limit("10/minute")
async def clear_memories(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count = await clear_all_memories(db, current_user.id)
    return ClearAllResponse(deleted=count)
