from services.queue.queue_manager_interface import IQueueFactory, IQueueManager
from services.queue.impl.aws_sqs_worker import AwsSqsService


from api import settings


class QueueService(IQueueFactory):

    @staticmethod
    def get_service(provider: str = settings.QUEUE_SERVICE_PROVIDER) -> IQueueManager or None:
        match provider:
            case "aws:sqs":
                return AwsSqsService()


if __name__ == '__main__':

    queue_handler = QueueService.get_service(provider=settings.QUEUE_SERVICE_PROVIDER)
    # queue_handler.create_queue(queue_name="test")
    queue_handler.create_queue(queue_name="neurona")
    # print(queue_handler.list_queues())
    queue_handler.write(queue_name="neurona", msg='Hello Earth!')
    queue_handler.write(queue_name="neurona", msg='Hello Moon!')
    queue_handler.write(queue_name="neurona", msg='Second queue message')
    # print(queue_handler.read(queue_name="test"))
    # queue_handler.purge(queue_name="test")
    # queue_handler.read(queue_name="test")
    # queue_handler.delete(queue_name="test")
    # print(queue_handler.list_queues())
    # queue_handler.delete(queue_name="contacts")
    # print(queue_handler.list_queues())
