# test_lambda_worker.py
# Exercises the SQS -> ECS launcher (lambda_handler.py), with ECS stubbed.

from unittest.mock import patch
from lambda_handler import lambda_handler
import json
import os

os.environ.setdefault("ECS_CLUSTER", "test-cluster")
os.environ.setdefault("ECS_TASK_DEFINITION", "test-task-def")
os.environ.setdefault("SUBNET_ID", "subnet-123")
os.environ.setdefault("SECURITY_GROUP_ID", "sg-123")
os.environ.setdefault("CONTAINER_NAME", "worker")

test_event = {
    "Records": [
        {
            "messageId": "test-message-1",
            "body": json.dumps({
                "Records": [
                    {
                        "eventName": "ObjectCreated:Put",
                        "s3": {
                            "bucket": {
                                "name": "openmedical"
                            },
                            "object": {
                                "key": "pdf/Pharmacology_Part_1.pdf"
                            }
                        }
                    }
                ]
            })
        }
    ]
}

with patch(
    "lambda_handler.ecs.run_task",
    return_value={"tasks": [{"taskArn": "arn:fake"}], "failures": []},
) as run_task:
    result = lambda_handler(test_event, None)

print(result)
assert result == {"batchItemFailures": []}, result
assert run_task.call_count == 1
print("OK: launcher invoked run_task once and reported no failures")
