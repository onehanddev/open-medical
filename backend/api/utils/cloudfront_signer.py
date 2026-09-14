import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


def create_policy(resource_url: str, expiration_seconds: int) -> tuple[bytes, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=expiration_seconds
    )

    policy = {
        "Statement": [
            {
                "Resource": resource_url,
                "Condition": {
                    "DateLessThan": {
                        "AWS:EpochTime": int(expires_at.timestamp())
                    }
                },
            }
        ]
    }

    compact_policy = json.dumps(
        policy,
        separators=(",", ":"),
    ).encode("utf-8")

    return compact_policy, expires_at


def sign_policy(policy: bytes, private_key_path: str) -> str:
    private_key = serialization.load_pem_private_key(
        Path(private_key_path).expanduser().read_bytes(),
        password=None,
    )

    signature = private_key.sign(
        policy,
        padding.PKCS1v15(),
        hashes.SHA1(),
    )

    return cloudfront_base64(signature)


def cloudfront_base64(value: bytes) -> str:
    return (
        base64.b64encode(value)
        .decode("utf-8")
        .replace("+", "-")
        .replace("=", "_")
        .replace("/", "~")
    )
