# test_lambda_worker.py

from backend.worker.s3_upload_fetch import lambda_handler
import json

test_event = {
    "Records": [
        {
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

lambda_handler(test_event, None)