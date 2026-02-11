from uuid import UUID

from ...domain.entities.certification import CertificationSubmission
from ..dtos.certification_dto import (
    CertificationResponseDTO,
    ChannelDeliveryDTO,
)
from ..ports.inbound import GetCertificationUseCase
from ..ports.outbound import CertificationRepository


class GetCertificationService(GetCertificationUseCase):
    """Application service implementing the get certification use case."""

    def __init__(self, repository: CertificationRepository):
        self._repository = repository

    async def execute(self, submission_id: UUID) -> CertificationResponseDTO | None:
        submission = await self._repository.get_by_id(submission_id)
        if not submission:
            return None
        return self._to_response_dto(submission)

    def _to_response_dto(self, submission: CertificationSubmission) -> CertificationResponseDTO:
        return CertificationResponseDTO(
            id=submission.id,
            status=submission.status,
            member_name=submission.member_name,
            certification_type=submission.certification_type,
            certification_date=submission.certification_date,
            photo_url=submission.photo_url,
            linkedin_url=submission.linkedin_url,
            personal_message=submission.personal_message,
            deliveries=[
                ChannelDeliveryDTO(
                    channel=d.channel,
                    status=d.status,
                    external_post_id=d.external_post_id,
                    error=d.error,
                    delivered_at=d.delivered_at,
                )
                for d in submission.deliveries
            ],
            created_at=submission.created_at,
        )
