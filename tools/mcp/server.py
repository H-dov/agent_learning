"""MCP 服务器实现 - 使用 FastMCP，支持 SSE 和 stdio"""

from __future__ import annotations

from fastmcp import FastMCP


mcp = FastMCP("agent-tools")


@mcp.tool()
def search(query: str, max_results: int = 5) -> list[dict]:
    """使用 DuckDuckGo 搜索网页"""
    from tools.builtins.search import search as search_impl
    print(f"MCP执行search工具，参数为{query}和{max_results}")
    return search_impl(query, max_results)


@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers"""
    print(f"MCP执行add工具，参数为{a}和{b}")
    return a + b


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers"""
    print(f"MCP执行multiply工具，参数为{a}和{b}")
    return a * b


def run_stdio():
    """运行 stdio 模式服务器"""
    mcp.run(transport="stdio")


def run_sse(host: str = "0.0.0.0", port: int = 8000):
    """运行 SSE 模式服务器"""
    mcp.run(transport="sse", host=host, port=port)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio", help="传输模式")
    parser.add_argument("--host", default="0.0.0.0", help="SSE 模式的主机地址")
    parser.add_argument("--port", type=int, default=8000, help="SSE 模式的端口")
    args = parser.parse_args()
    
    if args.transport == "sse":
        print(f"启动 MCP SSE 服务器: http://{args.host}:{args.port}")
        run_sse(args.host, args.port)
    else:
        run_stdio()
