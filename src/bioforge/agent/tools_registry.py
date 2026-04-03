"""Central registry that collects tools from all modules for AI agent use."""

from bioforge.modules.registry import ModuleRegistry


def collect_tools(registry: ModuleRegistry) -> list:
    """Collect all MCP tools from registered modules."""
    return registry.all_mcp_tools()


def collect_capabilities(registry: ModuleRegistry) -> dict:
    """Collect all module capabilities as a lookup dict."""
    return {cap.name: cap for cap in registry.all_capabilities()}
