import importlib.metadata
import logging

from bioforge.modules.base import (
    BioForgeModule,
    ModuleCapability,
    ModuleInfo,
    ModulePipelineStep,
)

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "bioforge.modules"


class ModuleRegistry:
    """Discovers, loads, and manages BioForgeModule instances."""

    def __init__(self) -> None:
        self._modules: dict[str, BioForgeModule] = {}

    async def discover_and_load(self) -> None:
        """Load modules from entry_points group 'bioforge.modules'."""
        eps = importlib.metadata.entry_points()
        group = eps.select(group=ENTRY_POINT_GROUP) if hasattr(eps, "select") else eps.get(ENTRY_POINT_GROUP, [])

        for ep in group:
            try:
                module_class = ep.load()
                instance = module_class()
                await instance.on_load()
                self._modules[instance.info().name] = instance
                logger.info("Loaded module: %s v%s", instance.info().name, instance.info().version)
            except Exception:
                logger.exception("Failed to load module: %s", ep.name)

    def register(self, module: BioForgeModule) -> None:
        """Manually register a module instance."""
        self._modules[module.info().name] = module

    def get_module(self, name: str) -> BioForgeModule | None:
        return self._modules.get(name)

    def list_modules(self) -> list[ModuleInfo]:
        return [m.info() for m in self._modules.values()]

    def all_capabilities(self) -> list[ModuleCapability]:
        caps = []
        for mod in self._modules.values():
            caps.extend(mod.capabilities())
        return caps

    def all_pipeline_steps(self) -> dict[str, ModulePipelineStep]:
        steps = {}
        for mod in self._modules.values():
            for step in mod.pipeline_steps():
                steps[step.step_type] = step
        return steps

    def all_mcp_tools(self) -> list:
        tools = []
        for mod in self._modules.values():
            tools.extend(mod.mcp_tools())
        return tools

    async def unload_all(self) -> None:
        for mod in self._modules.values():
            await mod.on_unload()
        self._modules.clear()
