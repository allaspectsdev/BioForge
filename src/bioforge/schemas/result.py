from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ResultRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    project_id: UUID
    pipeline_run_id: UUID | None
    result_type: str
    name: str
    summary: dict | None
    data: dict | None
    storage_key: str | None
    created_at: datetime
