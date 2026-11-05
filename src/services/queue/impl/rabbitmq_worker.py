from services.queue.queue_manager_interface import IQueueManager

import pika


class RabbitMQQueueManager(IQueueManager):
    def __init__(self, host='localhost'):
        try:
            self.connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
            self.channel = self.connection.channel()
            self.queues = dict()
        except Exception as e:
            print(e)

    def create_queue(self, queue_name: str):
        self.channel.queue_declare(queue=queue_name, durable=True)
        print(f'Queue {queue_name} created successfully.')

    def write(self, queue_name: str, msg: str):
        self.channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=msg,
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            ))
        print(f'Message "{msg}" sent to queue {queue_name}.')

    def read(self, queue_name: str):
        method_frame, header_frame, body = self.channel.basic_get(queue=queue_name)
        if method_frame:
            self.channel.basic_ack(method_frame.delivery_tag)
            print(f'Received message: {body.decode()}')
            return body.decode()
        else:
            print(f'No messages in queue {queue_name}.')
            return None

    def purge(self, queue_name: str):
        self.channel.queue_purge(queue=queue_name)
        print(f'Queue {queue_name} purged successfully.')

    def delete(self, queue_name: str):
        self.channel.queue_delete(queue=queue_name)
        print(f'Queue {queue_name} deleted successfully.')

    def list_queues(self):
        queues = self.channel.queue_declare(queue='', passive=True)
        queue_list = {method.queue for method in queues.method.frame if method.queue}
        print(f'List of queues: {queue_list}')
        return queue_list

    def close(self):
        self.connection.close()
        print('Connection closed.')




# Example usage:
if __name__ == "__main__":

    queue_manager = RabbitMQQueueManager()

    queue_name = 'test_queue'

    # Create a queue
    queue_manager.create_queue(queue_name)

    # Write a message to the queue
    queue_manager.write(queue_name, 'Hello, RabbitMQ!')

    # Read a message from the queue
    message = queue_manager.read(queue_name)

    # Purge the queue
    queue_manager.purge(queue_name)

    # Delete the queue
    queue_manager.delete(queue_name)

    # List queues
    queues = queue_manager.list_queues()

    # Close the connection
    queue_manager.close()