"""嵌入LRC歌词到FLAC文件"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def detect_encoding(file_path: Path) -> str:
    """
    检测文件编码
    
    Args:
        file_path: 文件路径
        
    Returns:
        检测到的编码名称
    """
    encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'utf-16', 'utf-16-le', 'utf-16-be']
    
    for encoding in encodings:
        try:
            content = file_path.read_text(encoding=encoding)
            if '周杰伦' in content or '词：' in content or '曲：' in content:
                return encoding
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    return 'utf-8'


def parse_lrc(lrc_content: str) -> str:
    """
    解析LRC歌词内容，返回纯文本格式
    
    Args:
        lrc_content: LRC格式的歌词内容
        
    Returns:
        格式化后的歌词文本
    """
    lines = lrc_content.strip().split('\n')
    result = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.startswith('[') and ']' in line:
            parts = line.split(']', 1)
            if len(parts) == 2:
                text = parts[1].strip()
                if text:
                    result.append(text)
        else:
            result.append(line)
    
    return '\n'.join(result)


def embed_lyrics_to_flac(
    flac_path: str,
    lrc_path: str | None = None,
    lyrics_text: str | None = None,
) -> str:
    """
    将LRC歌词嵌入到FLAC文件的元数据中
    
    Args:
        flac_path: FLAC文件路径
        lrc_path: LRC歌词文件路径（可选）
        lyrics_text: 直接提供的歌词文本（可选）
        
    Returns:
        操作结果信息
    """
    try:
        from mutagen.flac import FLAC
    except ImportError:
        return "错误: 需要安装 mutagen 库。请运行: uv add mutagen"
    
    flac_file = Path(flac_path).resolve()
    
    if not flac_file.exists():
        raise FileNotFoundError(f"FLAC文件不存在: {flac_path}")
    
    if not flac_file.suffix.lower() == '.flac':
        raise ValueError(f"文件不是FLAC格式: {flac_path}")
    
    if lrc_path is None and lyrics_text is None:
        lrc_path = str(flac_file.with_suffix('.lrc'))
    
    if lrc_path:
        lrc_file = Path(lrc_path).resolve()
        if not lrc_file.exists():
            raise FileNotFoundError(f"LRC文件不存在: {lrc_path}")
        
        encoding = detect_encoding(lrc_file)
        lrc_content = lrc_file.read_text(encoding=encoding)
        lyrics = parse_lrc(lrc_content)
    elif lyrics_text:
        lyrics = lyrics_text
    else:
        raise ValueError("必须提供 lrc_path 或 lyrics_text")
    
    audio = FLAC(str(flac_file))
    
    audio['LYRICS'] = lyrics
    audio['UNSYNCEDLYRICS'] = lyrics
    
    audio.save()
    
    return f"成功将歌词嵌入到 {flac_file.name}\n歌词行数: {len(lyrics.split(chr(10)))}"


def batch_embed_lyrics(
    directory: str,
    recursive: bool = False,
) -> str:
    """
    批量为目录中的FLAC文件嵌入歌词
    
    Args:
        directory: 目录路径
        recursive: 是否递归搜索子目录
        
    Returns:
        批量处理结果信息
    """
    dir_path = Path(directory).resolve()
    
    if not dir_path.exists():
        raise FileNotFoundError(f"目录不存在: {directory}")
    
    if not dir_path.is_dir():
        raise ValueError(f"不是目录: {directory}")
    
    if recursive:
        flac_files = list(dir_path.rglob('*.flac'))
    else:
        flac_files = list(dir_path.glob('*.flac'))
    
    if not flac_files:
        return f"目录中没有找到FLAC文件: {directory}"
    
    success_count = 0
    fail_count = 0
    results = []
    
    for flac_file in flac_files:
        lrc_file = flac_file.with_suffix('.lrc')
        
        if lrc_file.exists():
            try:
                result = embed_lyrics_to_flac(str(flac_file), str(lrc_file))
                success_count += 1
                results.append(f"[OK] {flac_file.name}")
            except Exception as e:
                fail_count += 1
                results.append(f"[FAIL] {flac_file.name}: {str(e)}")
        else:
            results.append(f"[SKIP] {flac_file.name}: 没有对应的LRC文件")
    
    summary = f"\n处理完成:\n成功: {success_count}\n失败: {fail_count}\n总计: {len(flac_files)}\n\n详细信息:\n"
    summary += '\n'.join(results)
    
    return summary


def extract_lyrics_from_flac(
    flac_path: str,
    output_lrc: str | None = None,
) -> str:
    """
    从FLAC文件中提取歌词
    
    Args:
        flac_path: FLAC文件路径
        output_lrc: 输出LRC文件路径（可选）
        
    Returns:
        歌词内容或操作结果
    """
    try:
        from mutagen.flac import FLAC
    except ImportError:
        return "错误: 需要安装 mutagen 库。请运行: uv add mutagen"
    
    flac_file = Path(flac_path).resolve()
    
    if not flac_file.exists():
        raise FileNotFoundError(f"FLAC文件不存在: {flac_path}")
    
    audio = FLAC(str(flac_file))
    
    lyrics = audio.get('LYRICS') or audio.get('UNSYNCEDLYRICS')
    
    if not lyrics:
        return f"FLAC文件中没有嵌入歌词: {flac_path}"
    
    lyrics_text = lyrics[0] if isinstance(lyrics, list) else lyrics
    
    if output_lrc:
        output_path = Path(output_lrc).resolve()
        output_path.write_text(lyrics_text, encoding='utf-8')
        return f"歌词已保存到: {output_path}"
    
    return lyrics_text


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  嵌入歌词: python lrc_embedder.py embed <flac_file> [lrc_file]")
        print("  批量处理: python lrc_embedder.py batch <directory> [--recursive]")
        print("  提取歌词: python lrc_embedder.py extract <flac_file> [output_lrc]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    try:
        if command == "embed":
            if len(sys.argv) < 3:
                print("错误: 需要指定FLAC文件路径")
                sys.exit(1)
            
            flac_path = sys.argv[2]
            lrc_path = sys.argv[3] if len(sys.argv) > 3 else None
            
            result = embed_lyrics_to_flac(flac_path, lrc_path)
            print(result)
            
        elif command == "batch":
            if len(sys.argv) < 3:
                print("错误: 需要指定目录路径")
                sys.exit(1)
            
            directory = sys.argv[2]
            recursive = "--recursive" in sys.argv
            
            result = batch_embed_lyrics(directory, recursive)
            print(result)
            
        elif command == "extract":
            if len(sys.argv) < 3:
                print("错误: 需要指定FLAC文件路径")
                sys.exit(1)
            
            flac_path = sys.argv[2]
            output_lrc = sys.argv[3] if len(sys.argv) > 3 else None
            
            result = extract_lyrics_from_flac(flac_path, output_lrc)
            print(result)
            
        else:
            print(f"未知命令: {command}")
            sys.exit(1)
            
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
