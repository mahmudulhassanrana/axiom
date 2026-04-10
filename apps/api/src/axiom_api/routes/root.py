from fastapi import APIRouter

from axiom_api import __version__
from axiom_api.schemas.meta import ServiceInfo

router = APIRouter(tags=["meta"])


@router.get(
    "/",
    response_model=ServiceInfo,
    summary="Service metadata",
)
def root() -> ServiceInfo:
    return ServiceInfo(service="axiom-api", version=__version__)
