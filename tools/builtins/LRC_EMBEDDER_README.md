# LRC歌词嵌入工具

将LRC格式歌词嵌入到FLAC音频文件的元数据中，让播放器能够显示同步歌词。

## 功能特性

- ✅ 将LRC歌词嵌入FLAC文件的元数据
- ✅ 自动匹配同名LRC文件
- ✅ 批量处理整个目录
- ✅ 从FLAC文件提取已嵌入的歌词
- ✅ 支持递归搜索子目录

## 安装依赖

```bash
uv add mutagen
```

## 使用方法

### 1. 单个文件嵌入歌词

```python
from tools.builtins.lrc_embedder import embed_lyrics_to_flac

# 方式1: 自动匹配同名LRC文件
embed_lyrics_to_flac("song.flac")  # 自动查找 song.lrc

# 方式2: 指定LRC文件路径
embed_lyrics_to_flac("song.flac", "lyrics.lrc")

# 方式3: 直接提供歌词文本
embed_lyrics_to_flac("song.flac", lyrics_text="歌词内容...")
```

### 2. 批量处理目录

```python
from tools.builtins.lrc_embedder import batch_embed_lyrics

# 处理当前目录
batch_embed_lyrics("./music")

# 递归处理子目录
batch_embed_lyrics("./music", recursive=True)
```

### 3. 提取已嵌入的歌词

```python
from tools.builtins.lrc_embedder import extract_lyrics_from_flac

# 提取并打印歌词
lyrics = extract_lyrics_from_flac("song.flac")
print(lyrics)

# 提取并保存到文件
extract_lyrics_from_flac("song.flac", "output.lrc")
```

### 4. 命令行使用

```bash
# 嵌入歌词
python -m tools.builtins.lrc_embedder embed song.flac

# 批量处理
python -m tools.builtins.lrc_embedder batch ./music

# 递归批量处理
python -m tools.builtins.lrc_embedder batch ./music --recursive

# 提取歌词
python -m tools.builtins.lrc_embedder extract song.flac output.lrc
```

## 文件命名规则

工具会自动匹配同名的FLAC和LRC文件：

```
music/
├── song1.flac
├── song1.lrc      # 自动匹配
├── song2.flac
├── song2.lrc      # 自动匹配
└── other.flac     # 没有对应的LRC文件，会被跳过
```

## LRC格式说明

LRC是标准的歌词文件格式，包含时间标签：

```lrc
[ti:歌曲名称]
[ar:艺术家]
[al:专辑名称]
[00:00.00]第一句歌词
[00:05.50]第二句歌词
[00:10.30]第三句歌词
```

## 元数据字段

歌词会被嵌入到以下FLAC元数据字段：

- `LYRICS` - 标准歌词字段
- `UNSYNCEDLYRICS` - 非同步歌词字段

大多数现代播放器都能识别这些字段并显示歌词。

## 支持的播放器

嵌入歌词后，以下播放器可以显示：

- foobar2000
- MusicBee
- AIMP
- VLC media player
- 其他支持FLAC元数据的播放器

## 注意事项

1. 确保FLAC文件没有被其他程序占用
2. LRC文件使用UTF-8编码
3. 批量处理时会跳过没有对应LRC文件的FLAC
4. 已有歌词的文件会被新歌词覆盖

## 示例

```python
# 完整示例
from tools.builtins.lrc_embedder import batch_embed_lyrics

# 批量处理音乐目录
result = batch_embed_lyrics(
    directory="D:/Music",
    recursive=True
)
print(result)
```

输出示例：
```
处理完成:
成功: 15
失败: 0
总计: 20

详细信息:
✓ song1.flac
✓ song2.flac
- song3.flac: 没有对应的LRC文件
✓ song4.flac
...
```
