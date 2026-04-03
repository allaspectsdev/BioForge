from fastapi import APIRouter

from bioforge.schemas.module import ModuleRead

router = APIRouter()


@router.get("/", response_model=list[ModuleRead])
async def list_modules():
    """List installed bioinformatics modules. Populated after module system is built."""
    return []


@router.get("/{module_name}", response_model=ModuleRead)
async def get_module(module_name: str):
    """Get module details. Populated after module system is built."""
    from fastapi import HTTPException

    raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")
