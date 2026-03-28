"""工具定义 - 简单的工具描述格式"""

from __future__ import annotations

from typing import Any, Callable, List


class Tool:
    """简单工具定义"""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict,
        fn: Callable,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.fn = fn

    def to_llm_format(self) -> dict:
        """转换为 LLM API 格式（OpenAI/Anthropic 通用）"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def execute(self, **kwargs) -> Any:
        """执行工具"""
        return self.fn(**kwargs)


# 内置工具列表
def get_builtin_tools() -> List[Tool]:
    """获取所有内置工具"""
    from .read import read_file
    from .write import write_file
    from .edit import edit_file
    from .bash import bash
    from .grep import grep
    from .find import find
    from .ls import ls
    from .search import search
    from .lrc_embedder import embed_lyrics_to_flac, batch_embed_lyrics, extract_lyrics_from_flac

    return [
        Tool(
            name="read",
            description="Read file contents. Use offset/limit for large files.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "offset": {"type": "integer", "description": "Start line (1-indexed)"},
                    "limit": {"type": "integer", "description": "Max lines to read"},
                },
                "required": ["path"],
            },
            fn=read_file,
        ),
        Tool(
            name="write",
            description="Write content to a file. Creates parent directories automatically.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["path", "content"],
            },
            fn=write_file,
        ),
        Tool(
            name="edit",
            description="Edit file by replacing exact text. old_text must match exactly.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "old_text": {"type": "string", "description": "Exact text to find"},
                    "new_text": {"type": "string", "description": "Replacement text"},
                },
                "required": ["path", "old_text", "new_text"],
            },
            fn=edit_file,
        ),
        Tool(
            name="bash",
            description="Execute bash command. Output truncated to 2000 lines or 30KB.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds"},
                },
                "required": ["command"],
            },
            fn=bash,
        ),
        Tool(
            name="grep",
            description="Search file contents for a pattern. Returns matching lines.",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Search pattern (regex)"},
                    "path": {"type": "string", "description": "Directory or file to search"},
                    "glob": {"type": "string", "description": "File pattern e.g. '*.py'"},
                },
                "required": ["pattern"],
            },
            fn=grep,
        ),
        Tool(
            name="find",
            description="Find files by glob pattern. Returns matching file paths.",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern e.g. '*.py'"},
                    "path": {"type": "string", "description": "Directory to search"},
                },
                "required": ["pattern"],
            },
            fn=find,
        ),
        Tool(
            name="ls",
            description="List directory contents. Returns entries with '/' suffix for directories.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"},
                },
            },
            fn=ls,
        ),
        Tool(
            name="search",
            description="Search the web for up-to-date information and return relevant results.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Maximum number of results"},
                },
                "required": ["query"],
            },
            fn=search,
        ),
        Tool(
            name="embed_lyrics",
            description="Embed LRC lyrics into a FLAC file's metadata. Automatically finds matching .lrc file if not specified.",
            parameters={
                "type": "object",
                "properties": {
                    "flac_path": {"type": "string", "description": "Path to the FLAC file"},
                    "lrc_path": {"type": "string", "description": "Path to the LRC file (optional, auto-detected if not provided)"},
                    "lyrics_text": {"type": "string", "description": "Direct lyrics text (optional, alternative to lrc_path)"},
                },
                "required": ["flac_path"],
            },
            fn=embed_lyrics_to_flac,
        ),
        Tool(
            name="batch_embed_lyrics",
            description="Batch embed lyrics to all FLAC files in a directory. Matches FLAC files with corresponding .lrc files.",
            parameters={
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Directory path containing FLAC and LRC files"},
                    "recursive": {"type": "boolean", "description": "Search subdirectories recursively"},
                },
                "required": ["directory"],
            },
            fn=batch_embed_lyrics,
        ),
        Tool(
            name="extract_lyrics",
            description="Extract embedded lyrics from a FLAC file.",
            parameters={
                "type": "object",
                "properties": {
                    "flac_path": {"type": "string", "description": "Path to the FLAC file"},
                    "output_lrc": {"type": "string", "description": "Output LRC file path (optional, prints to console if not provided)"},
                },
                "required": ["flac_path"],
            },
            fn=extract_lyrics_from_flac,
        ),
    ]


