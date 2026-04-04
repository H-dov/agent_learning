"""Chatbot with Tool Support - 支持工具调用的对话机器人（含 MCP 和 Skills 支持）"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.llm import call_llm
from core.node import Node, Flow, shared
from tools import get_tools, ToolExecutor
from tools.builtins.mcp_sse_client import (
    MCPToolAdapter,
    MCPToolCall,
    MCPToolResult,
    SyncMCPToolAdapter,
)
from tools.skill_manager import SkillManager, create_skill_manager

BASE_SYSTEM_PROMPT = (
    "你是一个会调用工具的助手。"
    "当问题涉及最新信息、模型版本、产品发布时间或事实核验时，优先先调用 search 工具，再基于搜索结果回答。"
    "若问题是本地文件/代码相关，优先使用 read/grep/find/ls 等本地工具。"
)

MCP_SERVERS = [
    {"name": "local", "url": "http://localhost:8000"},
]


class ChatNode(Node):
    """发送消息给 LLM，获取响应（可能包含 tool_calls）"""

    def exec(self, payload: Any) -> Tuple[str, Any]:
        messages = shared.get("messages", [])
        tools = shared.get("tools", [])
        
        user_input = shared.get("last_user_input", "")
        skill_manager = shared.get("skill_manager")
        
        system_prompt = BASE_SYSTEM_PROMPT
        
        if skill_manager and user_input:
            skill_prompt = skill_manager.build_skill_prompt(user_input)
            if skill_prompt:
                system_prompt = BASE_SYSTEM_PROMPT + skill_prompt
        
        assistant_message = call_llm(messages=messages, tools=tools, system_prompt=system_prompt)
        messages.append(assistant_message)
        shared["messages"] = messages

        if assistant_message.get("tool_calls"):
            return "tool_call", assistant_message

        return "output", assistant_message


class ToolCallNode(Node):
    """执行 LLM 返回的 tool_calls（支持本地工具和 MCP 远程工具）"""

    def exec(self, payload: Any) -> Tuple[str, Any]:
        response = payload
        messages = shared.get("messages", [])
        
        use_mcp = shared.get("use_mcp", False)
        
        if use_mcp:
            return self._exec_mcp(response, messages)
        else:
            return self._exec_local(response, messages)

    def _exec_local(self, response: Any, messages: list) -> Tuple[str, Any]:
        """使用本地工具执行器"""
        executor = shared.get("tool_executor")
        tool_calls = executor.parse_tool_calls(response)
        results = executor.execute_all(tool_calls)

        for tc, result in zip(tool_calls, results):
            print(f"  [Tool] 执行: {tc.name}({tc.arguments})")
            print(f"  [Tool] 结果: {result.content[:100]}...")
            messages.append(result.to_message())

        shared["messages"] = messages
        return "chat", None

    def _exec_mcp(self, response: Any, messages: list) -> Tuple[str, Any]:
        """使用 MCP 适配器执行工具"""
        adapter = shared.get("mcp_adapter")
        tool_calls = adapter.parse_tool_calls(response)
        results = adapter.execute_all(tool_calls)

        for tc, result in zip(tool_calls, results):
            print(f"  [Tool] 执行: {tc.name}({tc.arguments})")
            print(f"  [Tool] 结果: {result.content[:100]}...")
            messages.append(result.to_llm_message())

        shared["messages"] = messages
        return "chat", None


class OutputNode(Node):
    """输出助手回复"""

    def exec(self, payload: Any) -> Tuple[str, Any]:
        response = payload
        content = response.get("content", "")
        print(f"\n🤖 Assistant: {content}\n")
        return "default", None


def run_chat(
    use_mcp: bool = False, 
    mcp_servers: list | None = None,
    skills_dir: str | None = None,
) -> None:
    """运行对话循环
    
    Args:
        use_mcp: 是否使用 MCP 远程工具
        mcp_servers: MCP 服务器配置列表
        skills_dir: Skills 目录路径
    """
    print("=" * 60)
    print("🤖 Chatbot with Tools")
    print("=" * 60)
    
    skill_manager = create_skill_manager(skills_dir)
    skills_count = len(skill_manager.skills)
    
    if skills_count > 0:
        print(f"已加载 {skills_count} 个技能:")
        for skill in skill_manager.list_skills():
            desc = skill.description[:50] + "..." if len(skill.description) > 50 else skill.description
            print(f"  - {skill.name}: {desc}")
        print()
    
    if use_mcp:
        print("模式: MCP 远程工具")
        print(f"MCP 服务器: {mcp_servers or MCP_SERVERS}")
    else:
        print("模式: 本地工具")
        print("可用工具: read, write, edit, bash, grep, find, ls, search")
    
    print("输入 'quit' 或 'exit' 退出\n")

    shared.clear()
    shared["messages"] = []
    shared["use_mcp"] = use_mcp
    shared["skill_manager"] = skill_manager

    if use_mcp:
        adapter = SyncMCPToolAdapter()
        adapter.add_local_tools(get_tools())
        
        servers = mcp_servers or MCP_SERVERS
        connected_servers = []
        
        for server in servers:
            name = server.get("name", "unknown")
            url = server.get("url", "")
            if url:
                print(f"连接 MCP 服务器 '{name}' ({url})...")
                if adapter.connect_mcp_server(name, url):
                    connected_servers.append(name)
                    print(f"  ✓ 已连接")
                else:
                    print(f"  ✗ 连接失败")
        
        if not connected_servers:
            print("⚠️  没有可用的 MCP 服务器，将使用本地工具")
            shared["use_mcp"] = False
            shared["tools"] = [t.to_llm_format() for t in get_tools()]
            shared["tool_executor"] = ToolExecutor()
        else:
            shared["mcp_adapter"] = adapter
            shared["tools"] = adapter.get_all_tools_llm_format()
            
            tool_names = [t["function"]["name"] for t in shared["tools"]]
            print(f"\n可用工具 ({len(tool_names)} 个): {', '.join(tool_names[:10])}{'...' if len(tool_names) > 10 else ''}\n")
    else:
        shared["tools"] = [t.to_llm_format() for t in get_tools()]
        shared["tool_executor"] = ToolExecutor()

    chat = ChatNode()
    tool_call = ToolCallNode()
    output = OutputNode()

    chat - "tool_call" >> tool_call
    tool_call - "chat" >> chat
    chat - "output" >> output

    try:
        while True:
            user_input = input("👤 You: ").strip()

            if user_input.lower() in ("quit", "exit", "q"):
                print("\n再见！")
                break

            if not user_input:
                continue

            shared["last_user_input"] = user_input
            shared["messages"].append({"role": "user", "content": user_input})
            flow = Flow(chat)
            flow.run(None)
    finally:
        if use_mcp and shared.get("mcp_adapter"):
            shared["mcp_adapter"].close_all()


async def run_chat_async(
    use_mcp: bool = False, 
    mcp_servers: list | None = None,
    skills_dir: str | None = None,
) -> None:
    """异步版本的对话循环"""
    print("=" * 60)
    print("🤖 Chatbot with Tools (Async)")
    print("=" * 60)
    
    skill_manager = create_skill_manager(skills_dir)
    skills_count = len(skill_manager.skills)
    
    if skills_count > 0:
        print(f"已加载 {skills_count} 个技能:")
        for skill in skill_manager.list_skills():
            desc = skill.description[:50] + "..." if len(skill.description) > 50 else skill.description
            print(f"  - {skill.name}: {desc}")
        print()
    
    if use_mcp:
        print("模式: MCP 远程工具 (Async)")
        print(f"MCP 服务器: {mcp_servers or MCP_SERVERS}")
    else:
        print("模式: 本地工具")
        print("可用工具: read, write, edit, bash, grep, find, ls, search")
    
    print("输入 'quit' 或 'exit' 退出\n")

    shared.clear()
    shared["messages"] = []
    shared["use_mcp"] = use_mcp
    shared["skill_manager"] = skill_manager

    if use_mcp:
        adapter = MCPToolAdapter()
        adapter.add_local_tools(get_tools())
        
        servers = mcp_servers or MCP_SERVERS
        connected_servers = []
        
        for server in servers:
            name = server.get("name", "unknown")
            url = server.get("url", "")
            if url:
                print(f"连接 MCP 服务器 '{name}' ({url})...")
                if await adapter.connect_mcp_server(name, url):
                    connected_servers.append(name)
                    print(f"  ✓ 已连接")
                else:
                    print(f"  ✗ 连接失败")
        
        if not connected_servers:
            print("⚠️  没有可用的 MCP 服务器，将使用本地工具")
            shared["use_mcp"] = False
            shared["tools"] = [t.to_llm_format() for t in get_tools()]
            shared["tool_executor"] = ToolExecutor()
        else:
            shared["mcp_adapter_async"] = adapter
            shared["tools"] = adapter.get_all_tools_llm_format()
            
            tool_names = [t["function"]["name"] for t in shared["tools"]]
            print(f"\n可用工具 ({len(tool_names)} 个): {', '.join(tool_names[:10])}{'...' if len(tool_names) > 10 else ''}\n")
    else:
        shared["tools"] = [t.to_llm_format() for t in get_tools()]
        shared["tool_executor"] = ToolExecutor()

    chat = ChatNode()
    tool_call = ToolCallNode()
    output = OutputNode()

    chat - "tool_call" >> tool_call
    tool_call - "chat" >> chat
    chat - "output" >> output

    try:
        while True:
            user_input = input("👤 You: ").strip()

            if user_input.lower() in ("quit", "exit", "q"):
                print("\n再见！")
                break

            if not user_input:
                continue

            shared["last_user_input"] = user_input
            shared["messages"].append({"role": "user", "content": user_input})
            flow = Flow(chat)
            flow.run(None)
    finally:
        if use_mcp and shared.get("mcp_adapter_async"):
            await shared["mcp_adapter_async"].close_all()


def main() -> None:
    import argparse
    
    parser = argparse.ArgumentParser(description="Chatbot with Tool Support")
    parser.add_argument("--mcp", action="store_true", help="启用 MCP 远程工具")
    parser.add_argument("--mcp-url", type=str, help="MCP 服务器 URL (可多次指定)", action="append")
    parser.add_argument("--async", dest="use_async", action="store_true", help="使用异步模式")
    parser.add_argument("--skills-dir", type=str, help="Skills 目录路径")
    args = parser.parse_args()
    
    if not os.environ.get("DASH_SCOPE_API_KEY"):
        print("⚠️  提示：请先设置环境变量 DASH_SCOPE_API_KEY")
        print("   export DASH_SCOPE_API_KEY=your_key_here\n")

    mcp_servers = None
    if args.mcp_url:
        mcp_servers = [{"name": f"server{i}", "url": url} for i, url in enumerate(args.mcp_url)]

    if args.use_async:
        asyncio.run(run_chat_async(
            use_mcp=args.mcp, 
            mcp_servers=mcp_servers,
            skills_dir=args.skills_dir,
        ))
    else:
        run_chat(
            use_mcp=args.mcp, 
            mcp_servers=mcp_servers,
            skills_dir=args.skills_dir,
        )


if __name__ == "__main__":
    main()
