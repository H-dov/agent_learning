"""MCP SSE 客户端封装 - 支持通过 SSE 连接 MCP 服务器

提供 MCP 工具与 LLM 工具格式的双向转换：
- MCP tool -> LLM tool format
- LLM tool_calls -> MCP call_tool
- MCP tool result -> LLM tool message
"""

from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client


@dataclass
class MCPToolInfo:
    """MCP 工具信息"""
    name: str
    description: str
    input_schema: dict[str, Any]
    
    def to_llm_format(self) -> dict[str, Any]:
        """转换为 LLM API 格式（OpenAI/Anthropic 通用）"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


@dataclass
class MCPToolCall:
    """标准化的工具调用"""
    id: str
    name: str
    arguments: dict[str, Any]
    
    @classmethod
    def from_llm_tool_call(cls, tool_call: dict[str, Any]) -> "MCPToolCall":
        """从 LLM tool_calls 格式解析"""
        function = tool_call.get("function", {})
        arguments = function.get("arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        if not isinstance(arguments, dict):
            arguments = {}
        
        return cls(
            id=tool_call.get("id", str(uuid.uuid4())),
            name=function.get("name", ""),
            arguments=arguments,
        )


@dataclass
class MCPToolResult:
    """工具执行结果"""
    tool_call_id: str
    content: str
    is_error: bool = False
    
    def to_llm_message(self) -> dict[str, str]:
        """转换为 LLM tool message 格式"""
        return {
            "role": "tool",
            "tool_call_id": self.tool_call_id,
            "content": self.content,
        }


class MCPSSERClient:
    """MCP SSE 客户端 - 通过 SSE 连接 MCP 服务器
    
    使用方式:
        async with MCPSSERClient("http://localhost:8000/sse") as client:
            tools = client.tools
            result = await client.call_tool("add", {"a": 1, "b": 2})
    """
    
    def __init__(self, server_url: str, timeout: float = 30.0, sse_read_timeout: float = 300.0):
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self.sse_read_timeout = sse_read_timeout
        self.session: ClientSession | None = None
        self._tools: list[MCPToolInfo] = []
        self._cm = None
        self._read = None
        self._write = None
    
    @property
    def tools(self) -> list[MCPToolInfo]:
        return self._tools
    
    async def __aenter__(self) -> "MCPSSERClient":
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
    
    async def connect(self) -> None:
        """连接到 MCP 服务器"""
        sse_url = self.server_url
        if not sse_url.endswith("/sse"):
            sse_url = f"{sse_url}/sse"
        
        self._cm = sse_client(sse_url, timeout=self.timeout, sse_read_timeout=self.sse_read_timeout)
        self._read, self._write = await self._cm.__aenter__()
        
        self.session = ClientSession(self._read, self._write)
        await self.session.__aenter__()
        await self.session.initialize()
        
        await self._fetch_tools()
    
    async def _fetch_tools(self) -> None:
        """获取服务器上的工具列表"""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
        
        result = await self.session.list_tools()
        self._tools = [
            MCPToolInfo(
                name=tool.name,
                description=tool.description or "",
                input_schema=tool.inputSchema or {},
            )
            for tool in result.tools
        ]
    
    async def list_tools(self) -> list[MCPToolInfo]:
        """列出所有可用工具"""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
        await self._fetch_tools()
        return self._tools
    
    async def call_tool(self, name: str, arguments: dict[str, Any], tool_call_id: str | None = None) -> MCPToolResult:
        """调用 MCP 工具"""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
        
        call_id = tool_call_id or str(uuid.uuid4())
        
        try:
            result = await self.session.call_tool(name, arguments)
            
            content = self._extract_content(result)
            is_error = result.isError if hasattr(result, "isError") else False
            
            return MCPToolResult(
                tool_call_id=call_id,
                content=content,
                is_error=is_error,
            )
        except Exception as e:
            return MCPToolResult(
                tool_call_id=call_id,
                content=f"Error calling tool '{name}': {e}",
                is_error=True,
            )
    
    def _extract_content(self, result: Any) -> str:
        """从 MCP 结果中提取内容"""
        if hasattr(result, "content"):
            content = result.content
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            parts.append(item.get("text", ""))
                        else:
                            parts.append(str(item))
                    elif hasattr(item, "text"):
                        parts.append(item.text)
                    else:
                        parts.append(str(item))
                return "\n".join(parts)
            else:
                return str(content)
        return str(result)
    
    async def close(self) -> None:
        """关闭连接"""
        if self.session:
            try:
                await self.session.__aexit__(None, None, None)
            except Exception:
                pass
            self.session = None
        
        if self._cm:
            try:
                await self._cm.__aexit__(None, None, None)
            except Exception:
                pass
            self._cm = None
    
    def get_llm_tools(self) -> list[dict[str, Any]]:
        """获取 LLM 格式的工具列表"""
        return [tool.to_llm_format() for tool in self._tools]


class MCPToolAdapter:
    """MCP 工具适配器 - 整合本地工具和 MCP 远程工具
    
    使用方式:
        adapter = MCPToolAdapter()
        adapter.add_local_tools(get_builtin_tools())
        
        async with adapter.connect_mcp_server("my_server", "http://localhost:8000/sse"):
            tools = adapter.get_all_tools_llm_format()
            result = await adapter.execute_tool(tool_call)
    """
    
    def __init__(self) -> None:
        self.mcp_clients: dict[str, MCPSSERClient] = {}
        self._local_tools: dict[str, Any] = {}
        self._mcp_tools: dict[str, tuple[str, MCPToolInfo]] = {}
    
    def add_local_tools(self, tools: list[Any]) -> None:
        """添加本地工具"""
        for tool in tools:
            self._local_tools[tool.name] = tool
    
    @asynccontextmanager
    async def connect_mcp_server(self, name: str, server_url: str):
        """连接 MCP 服务器并注册其工具（上下文管理器）"""
        client = MCPSSERClient(server_url)
        
        try:
            await client.connect()
            self.mcp_clients[name] = client
            
            for tool in client.tools:
                self._mcp_tools[tool.name] = (name, tool)
            
            yield client
        finally:
            await client.close()
            if name in self.mcp_clients:
                del self.mcp_clients[name]
            to_remove = [k for k, v in self._mcp_tools.items() if v[0] == name]
            for k in to_remove:
                del self._mcp_tools[k]
    
    async def connect_mcp_server_simple(self, name: str, server_url: str) -> bool:
        """简单连接 MCP 服务器（需要手动管理连接生命周期）"""
        client = MCPSSERClient(server_url)
        
        try:
            await client.connect()
            self.mcp_clients[name] = client
            
            for tool in client.tools:
                self._mcp_tools[tool.name] = (name, tool)
            
            return True
        except Exception as e:
            print(f"Failed to connect to MCP server '{name}': {e}")
            return False
    
    def get_all_tools_llm_format(self) -> list[dict[str, Any]]:
        """获取所有工具的 LLM 格式"""
        tools = []
        
        for tool in self._local_tools.values():
            tools.append(tool.to_llm_format())
        
        for _, mcp_tool in self._mcp_tools.values():
            tools.append(mcp_tool.to_llm_format())
        
        return tools
    
    def parse_tool_calls(self, assistant_message: dict[str, Any]) -> list[MCPToolCall]:
        """解析 LLM 返回的 tool_calls"""
        tool_calls = assistant_message.get("tool_calls", [])
        return [MCPToolCall.from_llm_tool_call(tc) for tc in tool_calls]
    
    async def execute_tool(self, tool_call: MCPToolCall) -> MCPToolResult:
        """执行工具调用（自动路由到本地或 MCP）"""
        tool_name = tool_call.name
        
        if tool_name in self._local_tools:
            return await self._execute_local(tool_call)
        elif tool_name in self._mcp_tools:
            return await self._execute_mcp(tool_call)
        else:
            return MCPToolResult(
                tool_call_id=tool_call.id,
                content=f"Tool '{tool_name}' not found",
                is_error=True,
            )
    
    async def _execute_local(self, tool_call: MCPToolCall) -> MCPToolResult:
        """执行本地工具"""
        tool = self._local_tools.get(tool_call.name)
        if not tool:
            return MCPToolResult(
                tool_call_id=tool_call.id,
                content=f"Local tool '{tool_call.name}' not found",
                is_error=True,
            )
        
        try:
            result = tool.execute(**tool_call.arguments)
            content = self._stringify_result(result)
            return MCPToolResult(
                tool_call_id=tool_call.id,
                content=content,
                is_error=False,
            )
        except Exception as e:
            return MCPToolResult(
                tool_call_id=tool_call.id,
                content=f"Error: {e}",
                is_error=True,
            )
    
    async def _execute_mcp(self, tool_call: MCPToolCall) -> MCPToolResult:
        """执行 MCP 远程工具"""
        server_name, _ = self._mcp_tools.get(tool_call.name, (None, None))
        if not server_name:
            return MCPToolResult(
                tool_call_id=tool_call.id,
                content=f"MCP tool '{tool_call.name}' not found",
                is_error=True,
            )
        
        client = self.mcp_clients.get(server_name)
        if not client:
            return MCPToolResult(
                tool_call_id=tool_call.id,
                content=f"MCP server '{server_name}' not connected",
                is_error=True,
            )
        
        result = await client.call_tool(tool_call.name, tool_call.arguments, tool_call.id)
        return result
    
    def _stringify_result(self, value: Any) -> str:
        """将结果转换为字符串"""
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False)
        return str(value)
    
    async def execute_all(self, tool_calls: list[MCPToolCall]) -> list[MCPToolResult]:
        """执行所有工具调用"""
        results = []
        for tc in tool_calls:
            result = await self.execute_tool(tc)
            results.append(result)
        return results
    
    async def close_all(self) -> None:
        """关闭所有 MCP 连接"""
        for client in self.mcp_clients.values():
            await client.close()
        self.mcp_clients.clear()
        self._mcp_tools.clear()


class SyncMCPToolAdapter:
    """同步版本的 MCP 工具适配器 - 使用后台线程保持 SSE 连接"""
    
    def __init__(self) -> None:
        self._adapter = MCPToolAdapter()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread = None
    
    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None or self._loop.is_closed():
            import threading
            self._loop = asyncio.new_event_loop()
            
            def run_loop():
                asyncio.set_event_loop(self._loop)
                self._loop.run_forever()
            
            self._thread = threading.Thread(target=run_loop, daemon=True)
            self._thread.start()
        
        return self._loop
    
    def _run_async(self, coro):
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()
    
    def add_local_tools(self, tools: list[Any]) -> None:
        self._adapter.add_local_tools(tools)
    
    def connect_mcp_server(self, name: str, server_url: str) -> bool:
        return self._run_async(
            self._adapter.connect_mcp_server_simple(name, server_url)
        )
    
    def get_all_tools_llm_format(self) -> list[dict[str, Any]]:
        return self._adapter.get_all_tools_llm_format()
    
    def parse_tool_calls(self, assistant_message: dict[str, Any]) -> list[MCPToolCall]:
        return self._adapter.parse_tool_calls(assistant_message)
    
    def execute_tool(self, tool_call: MCPToolCall) -> MCPToolResult:
        return self._run_async(self._adapter.execute_tool(tool_call))
    
    def execute_all(self, tool_calls: list[MCPToolCall]) -> list[MCPToolResult]:
        return self._run_async(self._adapter.execute_all(tool_calls))
    
    def close_all(self) -> None:
        if self._loop:
            self._run_async(self._adapter.close_all())
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._loop = None


def create_sync_adapter() -> SyncMCPToolAdapter:
    """创建同步版本的适配器"""
    return SyncMCPToolAdapter()


async def demo_sse_client():
    """演示 SSE 客户端用法"""
    print("=" * 60)
    print("MCP SSE 客户端演示")
    print("=" * 60)
    
    async with MCPSSERClient("http://localhost:8000/sse") as client:
        print(f"已连接，发现 {len(client.tools)} 个工具:")
        for tool in client.tools:
            print(f"  - {tool.name}: {tool.description[:50]}...")
        
        print("\n调用工具 'add'...")
        result = await client.call_tool("add", {"a": 10, "b": 20})
        print(f"结果: {result.content}")
    
    print("\n连接已关闭")


if __name__ == "__main__":
    asyncio.run(demo_sse_client())
