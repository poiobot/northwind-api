from services.queue.queue_manager_interface import IQueueManager, IQueueFactory

from google.cloud import pubsub  # Updated import
from google.api_core import exceptions

from typing import Dict
import json

from api import settings

GOOGLE_QUEUES_CREDENTIALS = "/etc/gcp/padmi-cameras-monitor.json"


class GCPPubSubQueueManager(IQueueManager):

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.publisher = pubsub.PublisherClient()
        self.subscriber = pubsub.SubscriberClient()
        self.subscriptions = {}

    def create_queue(self, queue_name: str):
        """Create a new topic and subscription"""
        try:
            topic_path = self.publisher.topic_path(self.project_id, queue_name)
            subscription_path = self.subscriber.subscription_path(
                self.project_id, f"{queue_name}-sub"
            )

            # Create topic
            self.publisher.create_topic(request={"name": topic_path})

            # Create subscription
            self.subscriber.create_subscription(
                request={"name": subscription_path, "topic": topic_path}
            )

            self.subscriptions[queue_name] = subscription_path
            return True
        except exceptions.AlreadyExists:
            self.subscriptions[queue_name] = self.subscriber.subscription_path(
                self.project_id, f"{queue_name}-sub"
            )
            return True
        except Exception as e:
            raise Exception(f"Failed to create queue: {str(e)}")

    def write(self, queue_name: str, msg: str):
        """Publish a message to the topic"""
        try:
            topic_path = self.publisher.topic_path(self.project_id, queue_name)
            future = self.publisher.publish(topic_path, msg.encode('utf-8'))
            message_id = future.result()
            return message_id
        except Exception as e:
            raise Exception(f"Failed to write message: {str(e)}")

    def read(self, queue_name: str):
        """Pull a single message from the subscription"""
        try:
            subscription_path = self.subscriptions.get(queue_name)
            if not subscription_path:
                subscription_path = self.subscriber.subscription_path(
                    self.project_id, f"{queue_name}-sub"
                )
                self.subscriptions[queue_name] = subscription_path

            response = self.subscriber.pull(
                request={
                    "subscription": subscription_path,
                    "max_messages": 1,
                    "return_immediately": True
                }
            )

            if not response.received_messages:
                return None

            message = response.received_messages[0]
            self.subscriber.acknowledge(
                request={
                    "subscription": subscription_path,
                    "ack_ids": [message.ack_id]
                }
            )
            return message.message.data.decode('utf-8')
        except exceptions.NotFound:
            raise Exception(f"Subscription for queue {queue_name} not found")
        except Exception as e:
            raise Exception(f"Failed to read message: {str(e)}")

    def purge(self, queue_name: str):
        """Purge messages by recreating the subscription"""
        try:
            subscription_path = self.subscriptions.get(queue_name)
            if not subscription_path:
                subscription_path = self.subscriber.subscription_path(
                    self.project_id, f"{queue_name}-sub"
                )

            self.subscriber.delete_subscription(request={"subscription": subscription_path})
            topic_path = self.publisher.topic_path(self.project_id, queue_name)
            self.subscriber.create_subscription(
                request={"name": subscription_path, "topic": topic_path}
            )
            self.subscriptions[queue_name] = subscription_path
            return True
        except Exception as e:
            raise Exception(f"Failed to purge queue: {str(e)}")

    def delete(self, queue_name: str):
        """Delete the topic and subscription"""
        try:
            topic_path = self.publisher.topic_path(self.project_id, queue_name)
            subscription_path = self.subscriber.subscription_path(
                self.project_id, f"{queue_name}-sub"
            )

            try:
                self.subscriber.delete_subscription(request={"subscription": subscription_path})
            except exceptions.NotFound:
                pass

            self.publisher.delete_topic(request={"topic": topic_path})
            if queue_name in self.subscriptions:
                del self.subscriptions[queue_name]
            return True
        except Exception as e:
            raise Exception(f"Failed to delete queue: {str(e)}")

    def list_queues(self) -> Dict:
        """List all topics in the project"""
        try:
            queues = {}
            for topic in self.publisher.list_topics(request={"project": f"projects/{self.project_id}"}):
                queue_name = topic.name.split('/')[-1]
                queues[queue_name] = {
                    "name": queue_name,
                    "full_path": topic.name,
                    "subscription": f"{queue_name}-sub"
                }
            return queues
        except Exception as e:
            raise Exception(f"Failed to list queues: {str(e)}")


class QueueFactory(IQueueFactory):
    def get_service(self, provider: str) -> IQueueManager:
        """Factory method to get queue service instance"""
        if provider.lower() == "gcp":
            from os import environ
            project_id = environ.get("GOOGLE_CLOUD_PROJECT")
            if not project_id:
                raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set")
            return GCPPubSubQueueManager(project_id)
        else:
            raise ValueError(f"Unsupported provider: {provider}")


# Example usage
if __name__ == "__main__":
    try:
        factory = QueueFactory()
        queue_service = factory.get_service("gcp")

        queue_service.create_queue("test-queue")
        message_id = queue_service.write("test-queue", "Hello, World!")
        print(f"Published message ID: {message_id}")

        message = queue_service.read("test-queue")
        print(f"Received: {message}")

        queues = queue_service.list_queues()
        print(f"Queues: {queues}")

        queue_service.purge("test-queue")
        queue_service.delete("test-queue")
    except Exception as e:
        print(f"Error: {str(e)}")