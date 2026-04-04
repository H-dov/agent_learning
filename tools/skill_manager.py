"""Skill Manager - 管理 Skills 的加载、匹配和注入"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .skill_loader import load


@dataclass
class Skill:
    """技能定义"""
    name: str
    description: str
    content: str
    path: str
    metadata: dict[str, Any]
    
    @classmethod
    def from_file(cls, path: str) -> "Skill":
        """从 SKILL.md 文件加载技能"""
        metadata, content = load(path)
        return cls(
            name=metadata.get("name", Path(path).parent.name),
            description=metadata.get("description", ""),
            content=content,
            path=path,
            metadata=metadata,
        )
    
    def to_system_prompt(self) -> str:
        """转换为系统提示词格式"""
        return f"\n\n## Skill: {self.name}\n\n{self.content}\n\n"


class SkillManager:
    """技能管理器 - 加载、匹配和注入 Skills"""
    
    def __init__(self, skills_dir: str | None = None):
        self.skills: dict[str, Skill] = {}
        self._skills_dir = skills_dir
    
    def load_skills(self, skills_dir: str | None = None) -> int:
        """加载目录下所有 Skills"""
        dir_path = Path(skills_dir or self._skills_dir or self._default_skills_dir())
        
        if not dir_path.exists():
            return 0
        
        count = 0
        for skill_dir in dir_path.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    try:
                        skill = Skill.from_file(str(skill_file))
                        self.skills[skill.name] = skill
                        count += 1
                    except Exception as e:
                        print(f"Warning: Failed to load skill from {skill_file}: {e}")
        
        return count
    
    def _default_skills_dir(self) -> str:
        """获取默认 skills 目录"""
        return str(Path(__file__).parent / "skills")
    
    def get_skill(self, name: str) -> Skill | None:
        """获取指定技能"""
        return self.skills.get(name)
    
    def list_skills(self) -> list[Skill]:
        """列出所有技能"""
        return list(self.skills.values())
    
    def get_all_descriptions(self) -> dict[str, str]:
        """获取所有技能的描述"""
        return {name: skill.description for name, skill in self.skills.items()}
    
    def match_skills(self, query: str) -> list[Skill]:
        """根据查询匹配相关技能（简单关键词匹配）"""
        query_lower = query.lower()
        matched = []
        
        for skill in self.skills.values():
            if self._is_relevant(skill, query_lower):
                matched.append(skill)
        
        return matched
    
    def _is_relevant(self, skill: Skill, query: str) -> bool:
        """判断技能是否与查询相关"""
        name_lower = skill.name.lower()
        desc_lower = skill.description.lower()
        
        keywords = [name_lower]
        
        if name_lower == "pdf":
            keywords.extend(["pdf", ".pdf", "document", "merge", "split", "extract"])
        elif name_lower == "excel" or name_lower == "xlsx":
            keywords.extend(["excel", "xlsx", "spreadsheet", ".xlsx", ".xls"])
        elif name_lower == "image":
            keywords.extend(["image", "img", "picture", "photo", ".png", ".jpg", ".jpeg"])
        
        for kw in keywords:
            if kw in query:
                return True
        
        if name_lower in query:
            return True
        
        for word in name_lower.split():
            if len(word) > 2 and word in query:
                return True
        
        return False
    
    def build_skill_prompt(self, query: str, max_skills: int = 2) -> str:
        """根据查询构建技能提示词"""
        matched = self.match_skills(query)
        
        if not matched:
            return ""
        
        selected = matched[:max_skills]
        
        prompt_parts = ["\n\n# Relevant Skills\n"]
        prompt_parts.append("以下是与当前任务相关的技能指南，请参考这些指南完成任务：\n")
        
        for skill in selected:
            prompt_parts.append(f"\n---\n## Skill: {skill.name}\n")
            prompt_parts.append(skill.content[:3000])
            if len(skill.content) > 3000:
                prompt_parts.append("\n... (内容已截断)")
        
        return "".join(prompt_parts)
    
    def get_skill_summary(self) -> str:
        """获取技能摘要"""
        if not self.skills:
            return "No skills loaded."
        
        lines = ["Loaded Skills:"]
        for name, skill in self.skills.items():
            desc = skill.description[:60] + "..." if len(skill.description) > 60 else skill.description
            lines.append(f"  - {name}: {desc}")
        
        return "\n".join(lines)


def create_skill_manager(skills_dir: str | None = None) -> SkillManager:
    """创建并初始化 SkillManager"""
    manager = SkillManager(skills_dir)
    manager.load_skills()
    return manager
