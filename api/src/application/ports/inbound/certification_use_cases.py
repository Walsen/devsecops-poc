from abc import ABC, abstractmethod
from uuid import UUID

from ...dtos.certification_dto import (
    CertificationResponseDTO,
    CertificationTypeInfoDTO,
    CreateCertificationDTO,
)


class SubmitCertificationUseCase(ABC):
    """Inbound port for submitting a certification achievement."""

    @abstractmethod
    async def execute(self, dto: CreateCertificationDTO) -> CertificationResponseDTO:
        pass


class GetCertificationUseCase(ABC):
    """Inbound port for retrieving a certification submission."""

    @abstractmethod
    async def execute(self, submission_id: UUID) -> CertificationResponseDTO | None:
        pass


class ListCertificationTypesUseCase(ABC):
    """Inbound port for listing available certification types."""

    @abstractmethod
    def execute(self) -> list[CertificationTypeInfoDTO]:
        pass
