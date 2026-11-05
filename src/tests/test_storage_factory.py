"""StorageServiceFactory: STORAGE_PROVIDER picks the driver, and only that driver's settings are needed."""
from api import settings
from services.storage.storage_service_factory import StorageServiceFactory
from services.storage.impl.s3_compatible_storage import S3CompatibleStorageService
from services.storage.impl.local_storage import LocalStorageService


def test_r2_is_served_by_the_s3_compatible_driver_on_the_configured_endpoint(monkeypatch):
    monkeypatch.setattr(settings, "S3_ENDPOINT", "https://account.r2.example.test")

    service = StorageServiceFactory().get_service(provider="r2:cloudflare")

    assert isinstance(service, S3CompatibleStorageService)
    assert service.handler.meta.endpoint_url == "https://account.r2.example.test"


def test_local_provider_is_served_by_the_local_driver():
    assert isinstance(StorageServiceFactory().get_service(provider="local"), LocalStorageService)
