from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from ....application.commands import ScheduleMessageCommand
from ....application.dtos import CreateMessageDTO, MessageResponseDTO
from ....application.queries import GetMessageQuery
from ..dependencies import get_message_query, get_schedule_command

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post(
    "/",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule a message",
    description="Schedule a message for delivery across multiple channels.",
)
async def schedule_message(
    request: CreateMessageDTO,
    command: ScheduleMessageCommand = Depends(get_schedule_command),
) -> dict:
    """Schedule a message for async delivery."""
    message_id = await command.execute(request)
    return {"id": str(message_id), "status": "scheduled"}


@router.get(
    "/{message_id}",
    response_model=MessageResponseDTO,
    summary="Get message details",
    description="Retrieve message details including delivery status per channel.",
)
async def get_message(
    message_id: UUID,
    query: GetMessageQuery = Depends(get_message_query),
) -> MessageResponseDTO:
    """Get message by ID."""
    message = await query.execute(message_id)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message {message_id} not found",
        )
    return message
