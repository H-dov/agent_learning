"""内置工具模块 - 简化版

使用示例:
    from tools.builtins import get_builtin_tools

    # 获取所有工具
    tools = get_builtin_tools()

    # 直接执行
    result = tools[0].execute(path="some/file.py")

    # 转换为 LLM 格式
    llm_tools = [t.to_llm_format() for t in tools]

MCP 支持:
    from tools.builtins import MCPToolAdapter, SyncMCPToolAdapter

    # 同步模式
    adapter = SyncMCPToolAdapter()
    adapter.add_local_tools(get_builtin_tools())
    adapter.connect_mcp_server("my_server", "http://localhost:8000")
    tools = adapter.get_all_tools_llm_format()
"""

from .read import read_file
from .write import write_file
from .edit import edit_file
from .bash import bash
from .grep import grep
from .find import find
from .ls import ls
from .search import search
from .tool_def import Tool, get_builtin_tools
from .mcp_sse_client import (
    MCPSSERClient,
    MCPToolAdapter,
    MCPToolCall,
    MCPToolInfo,
    MCPToolResult,
    SyncMCPToolAdapter,
    create_sync_adapter,
)

__all__ = [
    "read_file",
    "write_file",
    "edit_file",
    "bash",
    "grep",
    "find",
    "ls",
    "search",
    "Tool",
    "get_builtin_tools",
    "MCPSSERClient",
    "MCPToolAdapter",
    "MCPToolCall",
    "MCPToolInfo",
    "MCPToolResult",
    "SyncMCPToolAdapter",
    "create_sync_adapter",
]
