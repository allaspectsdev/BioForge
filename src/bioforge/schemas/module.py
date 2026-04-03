from pydantic import BaseModel


class ModuleInfo(BaseModel):
    name: str
    version: str
    description: str
    author: str
    tags: list[str] = []


class ModuleCapabilityInfo(BaseModel):
    name: str
    description: str
    input_schema: dict
    output_schema: dict


class ModuleRead(BaseModel):
    info: ModuleInfo
    capabilities: list[ModuleCapabilityInfo] = []
