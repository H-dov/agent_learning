"""SubAgent - 子代理管理器

用于启动独立的子代理进程执行复杂任务，避免污染主 agent 上下文。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SubAgentResult:
    """子代理执行结果"""
    success: bool
    output: str
    error: str | None = None
    task: str | None = None
    duration: float | None = None


class SubAgentManager:
    """子代理管理器"""
    
    def __init__(
        self,
        runner_path: str | None = None,
        timeout: int = 300,
        max_concurrent: int = 3,
    ):
        self.runner_path = runner_path or self._default_runner_path()
        self.timeout = timeout
        self.max_concurrent = max_concurrent
    
    def _default_runner_path(self) -> str:
        """获取默认的 agent_runner.py 路径"""
        return str(Path(__file__).parent.parent / "agent_runner.py")
    
    def run_task(
        self,
        task: str,
        tools: list[str] | None = None,
        timeout: int | None = None,
    ) -> SubAgentResult:
        """启动子代理执行单个任务
        
        Args:
            task: 任务描述
            tools: 可用工具列表（可选）
            timeout: 超时时间（秒）
        
        Returns:
            SubAgentResult: 执行结果
        """
        import time
        start_time = time.time()
        
        runner_path = Path(self.runner_path)
        if not runner_path.exists():
            return SubAgentResult(
                success=False,
                output="",
                error=f"Agent runner not found: {self.runner_path}",
                task=task,
            )
        
        cmd = [
            sys.executable,
            str(runner_path),
            "--task", task,
        ]
        
        if tools:
            cmd.extend(["--tools", ",".join(tools)])
        
        actual_timeout = timeout or self.timeout
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=actual_timeout,
                cwd=str(Path.cwd()),
            )
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                return SubAgentResult(
                    success=True,
                    output=result.stdout.strip(),
                    error=result.stderr.strip() if result.stderr else None,
                    task=task,
                    duration=duration,
                )
            else:
                return SubAgentResult(
                    success=False,
                    output=result.stdout.strip(),
                    error=result.stderr.strip() or f"Exit code: {result.returncode}",
                    task=task,
                    duration=duration,
                )
                
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return SubAgentResult(
                success=False,
                output="",
                error=f"Task timed out after {actual_timeout} seconds",
                task=task,
                duration=duration,
            )
        except Exception as e:
            duration = time.time() - start_time
            return SubAgentResult(
                success=False,
                output="",
                error=str(e),
                task=task,
                duration=duration,
            )
    
    def run_tasks_parallel(
        self,
        tasks: list[str],
        tools: list[str] | None = None,
    ) -> list[SubAgentResult]:
        """并行执行多个任务
        
        Args:
            tasks: 任务列表
            tools: 可用工具列表
        
        Returns:
            list[SubAgentResult]: 结果列表
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = [None] * len(tasks)
        
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            futures = {
                executor.submit(self.run_task, task, tools): i
                for i, task in enumerate(tasks)
            }
            
            for future in as_completed(futures):
                i = futures[future]
                results[i] = future.result()
        
        return results


def run_subagent(task: str, tools: str | None = None, timeout: int = 300) -> str:
    """启动子代理执行任务（简化接口）
    
    Args:
        task: 任务描述
        tools: 可用工具列表，逗号分隔
        timeout: 超时时间（秒）
    
    Returns:
        str: 执行结果
    """
    manager = SubAgentManager(timeout=timeout)
    
    tool_list = None
    if tools:
        tool_list = [t.strip() for t in tools.split(",")]
    
    result = manager.run_task(task, tools=tool_list)
    
    if result.success:
        return result.output
    else:
        return f"[Error] {result.error}\n\n[Output]\n{result.output}"


def merge_results(results: list[SubAgentResult]) -> str:
    """合并多个子代理的结果
    
    Args:
        results: 结果列表
    
    Returns:
        str: 合并后的报告
    """
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    
    lines = ["# SubAgent Results Report\n"]
    
    if successful:
        lines.append(f"## Successful Tasks ({len(successful)})\n")
        for i, r in enumerate(successful, 1):
            lines.append(f"### Task {i}: {r.task[:50]}...")
            if r.duration:
                lines.append(f"Duration: {r.duration:.2f}s")
            lines.append(f"\n{r.output}\n")
    
    if failed:
        lines.append(f"\n## Failed Tasks ({len(failed)})\n")
        for i, r in enumerate(failed, 1):
            lines.append(f"### Task {i}: {r.task[:50]}...")
            lines.append(f"Error: {r.error}")
            if r.output:
                lines.append(f"Output: {r.output[:500]}...")
    
    return "\n".join(lines)
