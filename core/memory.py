"""Memory Management - 记忆压缩与管理"""

from __future__ import annotations

from .llm import call_llm_simple

COMPRESS_THRESHOLD = 20
KEEP_RECENT = 10


def compress_if_needed(messages: list) -> list:
    """如果消息过多，把早期对话压缩为摘要"""
    if len(messages) <= COMPRESS_THRESHOLD:
        return messages
    
    to_compress = messages[:-KEEP_RECENT]
    recent = messages[-KEEP_RECENT:]
    
    conv_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}"
        for m in to_compress
        if m["role"] != "system"
    )
    
    if not conv_text.strip():
        return messages
    
    summary = call_llm_simple(
        f"请用简洁的语言总结以下对话的关键内容，保留重要决策和结论：\n\n{conv_text}"
    )
    
    system_msgs = [m for m in messages if m["role"] == "system"]
    compressed = system_msgs + [
        {"role": "assistant", "content": f"[对话摘要]\n{summary}"}
    ] + recent
    
    return compressed


def get_memory_stats(messages: list) -> dict:
    """获取记忆统计信息"""
    total = len(messages)
    by_role = {}
    for m in messages:
        role = m.get("role", "unknown")
        by_role[role] = by_role.get(role, 0) + 1
    
    total_chars = sum(len(m.get("content", "")) for m in messages)
    
    return {
        "total_messages": total,
        "by_role": by_role,
        "total_chars": total_chars,
        "needs_compression": total > COMPRESS_THRESHOLD,
    }


def trim_tool_results(messages: list, max_content_length: int = 2000) -> list:
    """裁剪工具结果内容，避免过长"""
    result = []
    for m in messages:
        if m.get("role") == "tool":
            content = m.get("content", "")
            if len(content) > max_content_length:
                m = {**m, "content": content[:max_content_length] + "\n...[已截断]"}
        result.append(m)
    return result
