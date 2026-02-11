from ...domain.entities.certification import CERTIFICATION_INFO
from ..dtos.certification_dto import CertificationTypeInfoDTO
from ..ports.inbound import ListCertificationTypesUseCase


class ListCertificationTypesService(ListCertificationTypesUseCase):
    """Application service implementing the list certification types use case."""

    def execute(self) -> list[CertificationTypeInfoDTO]:
        return [
            CertificationTypeInfoDTO(
                id=cert_type,
                name=info["name"],
                hashtag=info["hashtag"],
                level=info["level"].value,
            )
            for cert_type, info in CERTIFICATION_INFO.items()
        ]
