from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from typing import Any

import aioboto3
from botocore.exceptions import ClientError


class ObjectStorage:
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str):
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket
        self._session = aioboto3.Session()

    @asynccontextmanager
    async def _client(self) -> AsyncGenerator[Any, None]:
        async with self._session.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        ) as client:
            yield client

    async def ensure_bucket(self) -> None:
        async with self._client() as client:
            try:
                await client.head_bucket(Bucket=self.bucket)
            except ClientError:
                await client.create_bucket(Bucket=self.bucket)

    async def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        async with self._client() as client:
            await client.put_object(
                Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
            )

    async def get(self, key: str) -> bytes:
        async with self._client() as client:
            resp = await client.get_object(Bucket=self.bucket, Key=key)
            return await resp["Body"].read()

    async def delete(self, key: str) -> None:
        async with self._client() as client:
            await client.delete_object(Bucket=self.bucket, Key=key)

    async def exists(self, key: str) -> bool:
        async with self._client() as client:
            try:
                await client.head_object(Bucket=self.bucket, Key=key)
                return True
            except ClientError:
                return False
