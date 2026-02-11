from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from ..value_objects.channel_type import ChannelType


class CertificationLevel(str, Enum):
    FOUNDATIONAL = "foundational"
    ASSOCIATE = "associate"
    PROFESSIONAL = "professional"
    SPECIALTY = "specialty"


class CertificationTypeEnum(str, Enum):
    CLOUD_PRACTITIONER = "cloud-practitioner"
    SOLUTIONS_ARCHITECT_ASSOCIATE = "solutions-architect-associate"
    SOLUTIONS_ARCHITECT_PROFESSIONAL = "solutions-architect-professional"
    DEVELOPER_ASSOCIATE = "developer-associate"
    SYSOPS_ADMINISTRATOR_ASSOCIATE = "sysops-administrator-associate"
    DEVOPS_ENGINEER_PROFESSIONAL = "devops-engineer-professional"
    DATABASE_SPECIALTY = "database-specialty"
    SECURITY_SPECIALTY = "security-specialty"
    MACHINE_LEARNING_SPECIALTY = "machine-learning-specialty"
    DATA_ANALYTICS_SPECIALTY = "data-analytics-specialty"
    ADVANCED_NETWORKING_SPECIALTY = "advanced-networking-specialty"
    SAP_SPECIALTY = "sap-specialty"


CERTIFICATION_INFO = {
    CertificationTypeEnum.CLOUD_PRACTITIONER: {
        "name": "Cloud Practitioner",
        "hashtag": "CloudPractitioner",
        "level": CertificationLevel.FOUNDATIONAL,
    },
    CertificationTypeEnum.SOLUTIONS_ARCHITECT_ASSOCIATE: {
        "name": "Solutions Architect Associate",
        "hashtag": "SolutionsArchitect",
        "level": CertificationLevel.ASSOCIATE,
    },
    CertificationTypeEnum.SOLUTIONS_ARCHITECT_PROFESSIONAL: {
        "name": "Solutions Architect Professional",
        "hashtag": "SolutionsArchitect",
        "level": CertificationLevel.PROFESSIONAL,
    },
    CertificationTypeEnum.DEVELOPER_ASSOCIATE: {
        "name": "Developer Associate",
        "hashtag": "AWSDeveloper",
        "level": CertificationLevel.ASSOCIATE,
    },
    CertificationTypeEnum.SYSOPS_ADMINISTRATOR_ASSOCIATE: {
        "name": "SysOps Administrator Associate",
        "hashtag": "SysOpsAdmin",
        "level": CertificationLevel.ASSOCIATE,
    },
    CertificationTypeEnum.DEVOPS_ENGINEER_PROFESSIONAL: {
        "name": "DevOps Engineer Professional",
        "hashtag": "DevOpsEngineer",
        "level": CertificationLevel.PROFESSIONAL,
    },
    CertificationTypeEnum.DATABASE_SPECIALTY: {
        "name": "Database Specialty",
        "hashtag": "AWSDatabase",
        "level": CertificationLevel.SPECIALTY,
    },
    CertificationTypeEnum.SECURITY_SPECIALTY: {
        "name": "Security Specialty",
        "hashtag": "AWSSecurity",
        "level": CertificationLevel.SPECIALTY,
    },
    CertificationTypeEnum.MACHINE_LEARNING_SPECIALTY: {
        "name": "Machine Learning Specialty",
        "hashtag": "AWSML",
        "level": CertificationLevel.SPECIALTY,
    },
    CertificationTypeEnum.DATA_ANALYTICS_SPECIALTY: {
        "name": "Data Analytics Specialty",
        "hashtag": "AWSAnalytics",
        "level": CertificationLevel.SPECIALTY,
    },
    CertificationTypeEnum.ADVANCED_NETWORKING_SPECIALTY: {
        "name": "Advanced Networking Specialty",
        "hashtag": "AWSNetworking",
        "level": CertificationLevel.SPECIALTY,
    },
    CertificationTypeEnum.SAP_SPECIALTY: {
        "name": "SAP on AWS Specialty",
        "hashtag": "AWSSAP",
        "level": CertificationLevel.SPECIALTY,
    },
}


class SubmissionStatus(str, Enum):
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    PARTIALLY_DELIVERED = "partially_delivered"
    FAILED = "failed"


class DeliveryStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"


@dataclass
class CertificationDelivery:
    channel: ChannelType
    status: DeliveryStatus = DeliveryStatus.PENDING
    external_post_id: str | None = None
    error: str | None = None
    delivered_at: datetime | None = None


@dataclass
class CertificationSubmission:
    id: UUID
    member_name: str
    certification_type: CertificationTypeEnum
    certification_date: datetime
    channels: list[ChannelType]
    status: SubmissionStatus = SubmissionStatus.SCHEDULED
    photo_url: str | None = None
    linkedin_url: str | None = None
    personal_message: str | None = None
    deliveries: list[CertificationDelivery] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        member_name: str,
        certification_type: CertificationTypeEnum,
        certification_date: datetime,
        channels: list[ChannelType],
        photo_url: str | None = None,
        linkedin_url: str | None = None,
        personal_message: str | None = None,
    ) -> "CertificationSubmission":
        submission = cls(
            id=uuid4(),
            member_name=member_name,
            certification_type=certification_type,
            certification_date=certification_date,
            channels=channels,
            photo_url=photo_url,
            linkedin_url=linkedin_url,
            personal_message=personal_message,
        )
        submission.deliveries = [CertificationDelivery(channel=channel) for channel in channels]
        return submission

    def get_certification_name(self) -> str:
        return CERTIFICATION_INFO[self.certification_type]["name"]

    def get_hashtag(self) -> str:
        return CERTIFICATION_INFO[self.certification_type]["hashtag"]

    def generate_post_content(self) -> str:
        """Generate the base post content for social media."""
        name = self.member_name
        cert_name = self.get_certification_name()
        hashtag = self.get_hashtag()

        content = f"🎉 Congratulations to {name}! 🎉\n\n"
        content += f"{name} has just earned the AWS {cert_name} certification!\n\n"
        if self.personal_message:
            content += f'"{self.personal_message}"\n\n'
        content += "Welcome to the club of AWS certified professionals! 🚀\n\n"
        content += f"#AWSCertified #{hashtag} #CloudCommunity #AWSCommunity"
        return content

    def mark_processing(self) -> None:
        self.status = SubmissionStatus.PROCESSING
        self.updated_at = datetime.now(UTC)

    def mark_channel_delivered(
        self, channel: ChannelType, external_post_id: str | None = None
    ) -> None:
        for delivery in self.deliveries:
            if delivery.channel == channel:
                delivery.status = DeliveryStatus.DELIVERED
                delivery.external_post_id = external_post_id
                delivery.delivered_at = datetime.now(UTC)
                break
        self._update_status()

    def mark_channel_failed(self, channel: ChannelType, error: str) -> None:
        for delivery in self.deliveries:
            if delivery.channel == channel:
                delivery.status = DeliveryStatus.FAILED
                delivery.error = error
                break
        self._update_status()

    def _update_status(self) -> None:
        delivered = sum(1 for d in self.deliveries if d.status == DeliveryStatus.DELIVERED)
        failed = sum(1 for d in self.deliveries if d.status == DeliveryStatus.FAILED)
        total = len(self.deliveries)

        if delivered == total:
            self.status = SubmissionStatus.DELIVERED
        elif failed == total:
            self.status = SubmissionStatus.FAILED
        elif delivered + failed == total:
            self.status = SubmissionStatus.PARTIALLY_DELIVERED
        self.updated_at = datetime.now(UTC)
