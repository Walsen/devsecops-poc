from ...domain.entities.certification import CertificationSubmission
from ..dtos.certification_dto import (
    CertificationResponseDTO,
    ChannelDeliveryDTO,
    CreateCertificationDTO,
)
from ..ports.inbound import SubmitCertificationUseCase
from ..ports.outbound import CertificationRepository, EventPublisher, UnitOfWork


class SubmitCertificationService(SubmitCertificationUseCase):
    """Application service implementing the submit certification use case."""

    def __init__(
        self,
        repository: CertificationRepository,
        event_publisher: EventPublisher,
        unit_of_work: UnitOfWork,
    ):
        self._repository = repository
        self._event_publisher = event_publisher
        self._uow = unit_of_work

    async def execute(self, dto: CreateCertificationDTO) -> CertificationResponseDTO:
        submission = CertificationSubmission.create(
            member_name=dto.member_name,
            certification_type=dto.certification_type,
            certification_date=dto.certification_date,
            channels=dto.channels,
            photo_url=str(dto.photo_url) if dto.photo_url else None,
            linkedin_url=str(dto.linkedin_url) if dto.linkedin_url else None,
            personal_message=dto.personal_message,
        )

        await self._repository.save(submission)
        await self._uow.commit()

        await self._event_publisher.publish(
            event_type="certification.submitted",
            payload={
                "submission_id": str(submission.id),
                "member_name": submission.member_name,
                "certification_type": submission.certification_type.value,
                "channels": [c.value for c in submission.channels],
                "content": submission.generate_post_content(),
                "photo_url": submission.photo_url,
                "linkedin_url": submission.linkedin_url,
            },
        )

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
