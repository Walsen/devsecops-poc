from abc import ABC, abstractmethod
from uuid import UUID

from ....domain.entities.certification import CertificationSubmission


class CertificationRepository(ABC):
    @abstractmethod
    async def save(self, submission: CertificationSubmission) -> None:
        pass

    @abstractmethod
    async def get_by_id(self, submission_id: UUID) -> CertificationSubmission | None:
        pass
