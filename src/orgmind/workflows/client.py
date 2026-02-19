from temporalio.client import Client
from temporalio.service import TLSConfig

from orgmind.platform.config import settings


async def get_temporal_client() -> Client:
    """
    Get a connected Temporal Client based on configuration settings.
    """
    # TODO: Add TLS support if needed for production
    tls_config: TLSConfig | None = None
    
    return await Client.connect(
        settings.TEMPORAL_HOST,
        namespace=settings.TEMPORAL_NAMESPACE,
        tls=tls_config,
    )
