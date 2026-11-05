from services.queue.queue_manager_interface import IQueueManager

import boto3
import datetime
from typing import Dict
import logging

from api import settings

logging.basicConfig(level=logging.INFO)


class LocalstackSqsService(IQueueManager):

    handler = boto3.client('sqs', endpoint_url=settings.LOCALSTACK_ENDPOINT_URL, use_ssl=False)

    def __init__(self):
        self.queues = dict()

    def create_queue(self, queue_name: str):
        # If you create an existing queue it simply returns the URL without mutating the original queue
        queue = self.handler.create_queue(QueueName=queue_name)
        self.queues[queue_name] = queue['QueueUrl']
        logging.info(f"Queue {queue_name} created: {self.queues[queue_name]}")

    def write(self, queue_name: str, msg: str):
        if not queue_name in self.queues:
            logging.info(f"Queue {queue_name} not found")
            return None
        enqueue_response = self.handler.send_message(QueueUrl=self.queues[queue_name], MessageBody=msg)
        logging.info(f"Queue.write[{queue_name}] -> wrote msgID({enqueue_response['MessageId']})")
        return enqueue_response['MessageId']

    def read(self, queue_name: str):
        if queue_name not in self.queues:
            logging.info(f"Queue {queue_name} not found")
            return None
        messages = self.handler.receive_message(QueueUrl=self.queues[queue_name], MaxNumberOfMessages=1)
        if messages.get('Messages', None) is None:
            logging.info(f"Queue {queue_name} EMPTY at {datetime.datetime.now().strftime('%Y-%m-%y %H:%M:%S.%f')}")
            return None
        logging.info(f"Queue.read[{queue_name}] -> read msgID({messages['Messages'][0]['MessageId']})")
        self.handler.delete_message(QueueUrl=self.queues[queue_name],
                                    ReceiptHandle=messages['Messages'][0]['ReceiptHandle'])
        return messages['Messages'][0]['Body']

    def purge(self, queue_name: str):
        if queue_name not in self.queues:
            logging.info(f"Queue {queue_name} not found")
            return None
        response = self.handler.purge_queue(QueueUrl=self.queues[queue_name])
        logging.info(f"Queuu[{queue_name}] -> purged")
        return response

    def delete(self, queue_name: str):
        if queue_name not in self.queues:
            logging.info(f"Queue {queue_name} not found")
            return None
        response = self.handler.delete_queue(QueueUrl=self.queues[queue_name])
        del self.queues[queue_name]
        logging.info(f"Queue[{queue_name}] -> deleted")
        return response

    def list_queues(self) -> Dict:
        return self.queues


if __name__ == '__main__':
    queue = LocalstackSqsService()
    queue.create_queue(queue_name='test')
    print(queue.list_queues())
    queue.write(queue_name='test', msg='Hello Earth!')
    queue.write(queue_name='test', msg='Hello Moon!')
    print(queue.read(queue_name='test'))
    queue.purge(queue_name='test')
    queue.read(queue_name='test')
    queue.delete(queue_name='test')
    print(queue.list_queues())
