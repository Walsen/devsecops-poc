"""Certifications API endpoints with user-scoped access control."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from ....application.dtos.certification_dto import (
    CertificationResponseDTO,
    CertificationTypeInfoDTO,
    CreateCertificationDTO,
)
from ....application.ports.inbound import (
    GetCertificationUseCase,
    ListCertificationTypesUseCase,
    SubmitCertificationUseCase,
)
from ...middleware.auth import AuthenticatedUser, require_auth
from ..dependencies import (
    get_certification_service,
    get_certification_use_case,
    get_list_certification_types_use_case,
)

router = APIRouter(prefix="/certifications", tags=["certifications"])


@router.post(
    "",
    response_model=CertificationResponseDTO,
    status_code=status.HTTP_201_CREATED,
)
async def submit_certification(
    dto: CreateCertificationDTO,
    user: Annotated[AuthenticatedUser, Depends(require_auth)],
    use_case: SubmitCertificationUseCase = Depends(get_certification_service),
) -> CertificationResponseDTO:
    """Submit a new certification achievement for announcement.

    Security: Requires authentication. User ID is automatically set from token.
    """
    # Security: Override user_id from authenticated token (prevent spoofing)
    dto_with_user = CreateCertificationDTO(
        certification_type=dto.certification_type,
        member_name=dto.member_name,
        certification_date=dto.certification_date,
        channels=dto.channels,
        photo_url=dto.photo_url,
        linkedin_url=dto.linkedin_url,
        personal_message=dto.personal_message,
        user_id=user.user_id,
    )
    return await use_case.execute(dto_with_user)


@router.get("/{submission_id}", response_model=CertificationResponseDTO)
async def get_submission(
    submission_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(require_auth)],
    use_case: GetCertificationUseCase = Depends(get_certification_use_case),
) -> CertificationResponseDTO:
    """Get the status of a certification submission.

    Security: Users can only access their own submissions (IDOR prevention).
    """
    result = await use_case.execute(submission_id, user_id=user.user_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found",
        )
    return result


@router.get("/types/", response_model=list[CertificationTypeInfoDTO])
async def list_certification_types(
    use_case: ListCertificationTypesUseCase = Depends(get_list_certification_types_use_case),
) -> list[CertificationTypeInfoDTO]:
    """List all available AWS certification types.

    Note: This endpoint is public (no auth required).
    """
    return use_case.execute()
