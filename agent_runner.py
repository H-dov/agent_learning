"""Agent Runner - 独立的子代理运行器

用于在独立进程中运行子代理，执行复杂任务后返回结果。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.llm import call_llm
from core.node import Node, Flow, shared
from tools import get_tools, ToolExecutor


SUBAGENT_SYSTEM_PROMPT = """你是一个独立的子代理，负责执行主代理分配的特定任务。

你的职责：
1. 完成分配给你的任务
2. 只使用必要的工具
3. 返回简洁明确的结果

注意：
- 不要输出过多的中间过程
- 直接给出最终结果
- 如果任务无法完成，说明原因
"""


class SubAgentChatNode(Node):
    """子代理聊天节点"""
    
    def exec(self, payload):
        messages = shared.get("messages", [])
        tools = shared.get("tools", [])
        
        response = call_llm(
            messages=messages,
            tools=tools,
            system_prompt=SUBAGENT_SYSTEM_PROMPT,
        )
        messages.append(response)
        shared["messages"] = messages
        
        if response.get("tool_calls"):
            return "tool_call", response
        
        return "output", response


class SubAgentToolNode(Node):
    """子代理工具执行节点"""
    
    def exec(self, payload):
        response = payload
        messages = shared.get("messages", [])
        executor = shared.get("tool_executor")
        
        tool_calls = executor.parse_tool_calls(response)
        results = executor.execute_all(tool_calls)
        
        for tc, result in zip(tool_calls, results):
            messages.append(result.to_message())
        
        shared["messages"] = messages
        return "chat", None


class SubAgentOutputNode(Node):
    """子代理输出节点"""
    
    def exec(self, payload):
        response = payload
        content = response.get("content", "")
        shared["final_output"] = content
        return "default", None


def run_subagent_task(
    task: str,
    tools: list[str] | None = None,
    max_iterations: int = 10,
) -> str:
    """运行子代理任务
    
    Args:
        task: 任务描述
        tools: 可用工具列表（可选）
        max_iterations: 最大迭代次数
    
    Returns:
        str: 执行结果
    """
    shared.clear()
    shared["messages"] = []
    
    all_tools = get_tools()
    
    if tools:
        all_tools = [t for t in all_tools if t.name in tools]
    
    shared["tools"] = [t.to_llm_format() for t in all_tools]
    shared["tool_executor"] = ToolExecutor()
    shared["final_output"] = ""
    
    shared["messages"].append({"role": "user", "content": task})
    
    chat = SubAgentChatNode()
    tool = SubAgentToolNode()
    output = SubAgentOutputNode()
    
    chat - "tool_call" >> tool
    tool - "chat" >> chat
    chat - "output" >> output
    
    flow = Flow(chat)
    
    iterations = 0
    while iterations < max_iterations:
        flow.run(None)
        
        if shared.get("final_output"):
            break
        
        iterations += 1
    
    return shared.get("final_output", "Task completed but no output generated.")


def main():
    parser = argparse.ArgumentParser(description="SubAgent Runner")
    parser.add_argument("--task", type=str, required=True, help="Task to execute")
    parser.add_argument("--tools", type=str, help="Available tools (comma-separated)")
    parser.add_argument("--max-iterations", type=int, default=10, help="Max iterations")
    args = parser.parse_args()
    
    tools = None
    if args.tools:
        tools = [t.strip() for t in args.tools.split(",")]
    
    result = run_subagent_task(
        task=args.task,
        tools=tools,
        max_iterations=args.max_iterations,
    )
    
    print(result)


if __name__ == "__main__":
    main()
