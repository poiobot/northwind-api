from services.storage.storage_service_interface import IStorageService, IStorageServiceFactory


class StorageServiceFactory(IStorageServiceFactory):
    """Lazy-import storage implementations to avoid import errors from missing env vars."""

    def get_service(self, provider: str) -> IStorageService or None:
        match provider:
            case "aws:s3":
                from services.storage.impl.aws_storage_service import AWSStorageService
                return AWSStorageService()
            case "s3" | "r2:cloudflare" | "r2" | "minio":
                from services.storage.impl.s3_compatible_storage import S3CompatibleStorageService
                return S3CompatibleStorageService()
            case "liquidweb":
                from services.storage.impl.liquidweb_storage_service import LiquidWebStorageService
                return LiquidWebStorageService()
            case "local":
                from services.storage.impl.local_storage import LocalStorageService
                return LocalStorageService()
            case _:
                from services.storage.impl.s3_compatible_storage import S3CompatibleStorageService
                return S3CompatibleStorageService()



if __name__ == '__main__':

    handler = StorageServiceFactory().get_service("liquidweb")
    handler.mount(volume='keeper-domain-ok-drive')
    oid = handler.upload(volume='keeper-domain-ok-drive', file_path='/Users/jnajera/Downloads/green_monster.jpg', target_path='images')
    handler.download(volume='keeper-domain-ok-drive', file_path=oid, target_file_path="/tmp/image.jpg")
    url = handler.get_file_url(volume='keeper-domain-ok-drive', file_path=oid, expires=30)
    print(url)
    handler.delete(volume='keeper-domain-ok-drive', file_path=oid)
