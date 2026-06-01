#!/usr/bin/env python3
"""
构建前脚本：Obsidian wikilink → MkDocs markdown链接
在临时副本上操作，绝不修改原始 docs/ 文件

用法: python3 scripts/pre-build.py
流程:
  1. 将 docs/ 复制到 .build-docs/ (临时目录)
  2. 转换 .build-docs/ 中所有 [[wikilink]] 为 [text](url) 格式
  3. mkdocs.yml 的 docs_dir 指向 .build-docs/
  4. mkdocs build 从 .build-docs/ 构建
"""

import re
import os
import shutil
import sys
from pathlib import Path

VAULT_ROOT = Path(__file__).parent.parent / "docs"
BUILD_DOCS = Path(__file__).parent.parent / ".build-docs"


def convert_wikilinks(content: str) -> str:
    """转换 [[链接]] 为 MkDocs 兼容的 Markdown 链接格式。"""

    def replace_wikilink(match):
        inner = match.group(1)

        # 解析 [[link|text]] 或 [[link]]
        if '|' in inner:
            target, display = inner.split('|', 1)
        else:
            target = inner
            display = target

        # 处理锚点 #section
        anchor = ""
        if '#' in target:
            target, anchor_part = target.split('#', 1)
            anchor = f"#{anchor_part.lower().replace(' ', '-')}"

        target = target.strip()

        # 如果没有文件扩展名，加 .md
        if not target.endswith('.md'):
            if target.endswith('/'):
                target = target + '00-目录'
            target_path = target + '.md'
        else:
            target_path = target

        url = target_path + anchor
        return f"[{display}]({url})"

    content = re.sub(r'\[\[([^\]]+)\]\]', replace_wikilink, content)
    return content


def prepare_build_docs():
    """复制 docs/ 到 .build-docs/ 并转换 wikilink"""

    # 清理旧的构建目录
    if BUILD_DOCS.exists():
        shutil.rmtree(BUILD_DOCS)

    # 复制整个 docs/ 目录
    shutil.copytree(VAULT_ROOT, BUILD_DOCS)
    print(f"📁 已复制 docs/ → .build-docs/")

    # 遍历 .build-docs/ 中的所有 .md 文件，转换 wikilink
    converted = 0
    skipped = 0

    for md_file in BUILD_DOCS.rglob("*.md"):
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            if '[[' not in content:
                skipped += 1
                continue

            new_content = convert_wikilinks(content)

            if new_content != content:
                with open(md_file, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                rel = md_file.relative_to(BUILD_DOCS)
                print(f"  ✅ 转换: {rel}")
                converted += 1
            else:
                skipped += 1

        except Exception as e:
            print(f"  ❌ 失败: {md_file.relative_to(BUILD_DOCS)} — {e}")

    print(f"\n📊 转换完成: {converted} 个文件转换, {skipped} 个无需处理")
    print(f"💡 原始 docs/ 未被修改，Obsidian 继续用 [[wikilink]]")


def cleanup():
    """构建完成后清理 .build-docs/"""
    if BUILD_DOCS.exists():
        shutil.rmtree(BUILD_DOCS)
        print(f"🧹 已清理 .build-docs/")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        cleanup()
    else:
        prepare_build_docs()
