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
    use_case: SubmitCertificationUseCase = Depends(get_certification_service),
):
    """Submit a new certification achievement for announcement."""
    return await use_case.execute(dto)


@router.get("/{submission_id}", response_model=CertificationResponseDTO)
async def get_submission(
    submission_id: UUID,
    use_case: GetCertificationUseCase = Depends(get_certification_use_case),
):
    """Get the status of a certification submission."""
    result = await use_case.execute(submission_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found",
        )
    return result


@router.get("/types/", response_model=list[CertificationTypeInfoDTO])
async def list_certification_types(
    use_case: ListCertificationTypesUseCase = Depends(get_list_certification_types_use_case),
):
    """List all available AWS certification types."""
    return use_case.execute()
