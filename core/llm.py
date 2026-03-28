from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def call_llm(
    prompt: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    tools: list[dict[str, Any]] | None = None,
    system_prompt: str | None = None,
) -> str | dict[str, Any]:
    """
    统一 LLM 调用入口。

    - 兼容旧用法: 传 prompt（且不传 messages/tools）时返回字符串
    - 工具模式: 传 messages 或 tools 时返回 assistant message 字典
    """
    client = OpenAI(
        api_key=os.environ.get("DASH_SCOPE_API_KEY"),
        base_url=os.environ.get("DASH_SCOPE_BASE_URL"),
    )

    if messages is not None:
        msgs = list(messages)
    elif prompt is not None:
        msgs = [{"role": "user", "content": prompt}]
    else:
        raise ValueError("Either prompt or messages must be provided")

    if system_prompt:
        msgs = [{"role": "system", "content": system_prompt}, *msgs]

    kwargs: dict[str, Any] = {
        "model": "qwen3-max-2026-01-23",
        "messages": msgs,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    response = client.chat.completions.create(**kwargs)
    message = response.choices[0].message

    # 兼容老示例（chatbot/workflow）: 只要是简单 prompt 模式就返回字符串
    if messages is None and tools is None and system_prompt is None:
        return message.content or ""

    result: dict[str, Any] = {
        "role": "assistant",
        "content": message.content or "",
    }

    reasoning_content = getattr(message, "reasoning_content", None)
    if reasoning_content:
        result["reasoning_content"] = reasoning_content

    if message.tool_calls:
        result["tool_calls"] = [tool_call.model_dump() for tool_call in message.tool_calls]

    return result


if __name__ == "__main__":
    print("Basic:", call_llm("用一句话解释什么是 Agent。"))
