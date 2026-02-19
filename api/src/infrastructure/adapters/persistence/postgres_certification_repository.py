from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ....application.ports.outbound import CertificationRepository
from ....domain.entities.certification import (
    CertificationDelivery,
    CertificationSubmission,
    CertificationTypeEnum,
    DeliveryStatus,
    SubmissionStatus,
)
from ....domain.value_objects.channel_type import ChannelType
from ...persistence.models import (
    CertificationDeliveryModel,
    CertificationSubmissionModel,
    _naive_utc,
)


class PostgresCertificationRepository(CertificationRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, submission: CertificationSubmission) -> None:
        model = CertificationSubmissionModel(
            id=submission.id,
            member_name=submission.member_name,
            certification_type=submission.certification_type.value,
            certification_date=_naive_utc(submission.certification_date),
            photo_url=submission.photo_url,
            linkedin_url=submission.linkedin_url,
            personal_message=submission.personal_message,
            status=submission.status.value,
            created_at=_naive_utc(submission.created_at),
            updated_at=_naive_utc(submission.updated_at),
        )

        for delivery in submission.deliveries:
            delivery_model = CertificationDeliveryModel(
                submission_id=submission.id,
                channel=delivery.channel.value,
                status=delivery.status.value,
                external_post_id=delivery.external_post_id,
                error=delivery.error,
                delivered_at=_naive_utc(delivery.delivered_at),
            )
            model.deliveries.append(delivery_model)

        self._session.add(model)

    async def get_by_id(self, submission_id: UUID) -> CertificationSubmission | None:
        stmt = (
            select(CertificationSubmissionModel)
            .options(selectinload(CertificationSubmissionModel.deliveries))
            .where(CertificationSubmissionModel.id == submission_id)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return self._to_entity(model)

    def _to_entity(self, model: CertificationSubmissionModel) -> CertificationSubmission:
        deliveries = [
            CertificationDelivery(
                channel=ChannelType(d.channel),
                status=DeliveryStatus(d.status),
                external_post_id=d.external_post_id,
                error=d.error,
                delivered_at=d.delivered_at,
            )
            for d in model.deliveries
        ]

        return CertificationSubmission(
            id=model.id,
            member_name=model.member_name,
            certification_type=CertificationTypeEnum(model.certification_type),
            certification_date=model.certification_date,
            channels=[d.channel for d in deliveries],
            status=SubmissionStatus(model.status),
            photo_url=model.photo_url,
            linkedin_url=model.linkedin_url,
            personal_message=model.personal_message,
            deliveries=deliveries,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
