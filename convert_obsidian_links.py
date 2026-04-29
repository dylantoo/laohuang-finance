#!/usr/bin/env python3
"""
Obsidian → MkDocs 链接转换脚本

把 Obsidian 的 [[链接]] 格式转为 MkDocs 兼容的 Markdown 链接格式。
用法: python3 convert_obsidian_links.py [vault_path]
"""

import re
import os
import sys
from pathlib import Path

def convert_wikilinks(content: str, file_path: Path, vault_root: Path) -> str:
    """
    转换 [[链接]] 和 [[链接|显示名]] 为 Markdown 链接格式。
    
    规则：
    - [[文件名]] → [文件名](文件名.md)
    - [[路径/文件名|显示名]] → [显示名](路径/文件名.md)
    - [[文件名#标题]] → [文件名#标题](文件名.md#标题)
    """
    
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
        
        # 处理路径
        target = target.strip()
        
        # 如果没有文件扩展名，加 .md
        if not target.endswith('.md'):
            # 检查是否是目录索引（00-目录）
            if target.endswith('/'):
                target = target + '00-目录'
            target_path = target + '.md'
        else:
            target_path = target
        
        # 构造 Markdown 链接
        url = target_path + anchor
        return f"[{display}]({url})"
    
    # 转换 [[wikilinks]]
    content = re.sub(r'\[\[([^\]]+)\]\]', replace_wikilink, content)
    
    return content


def convert_vault(vault_path: str):
    """遍历整个 Obsidian vault，转换所有 .md 文件中的 [[链接]]"""
    
    vault = Path(vault_path).expanduser().resolve()
    if not vault.exists():
        print(f"❌ Vault 路径不存在: {vault}")
        return
    
    md_files = list(vault.rglob("*.md"))
    # 排除 .obsidian/ 目录
    md_files = [f for f in md_files if '.obsidian' not in f.parts]
    
    converted = 0
    skipped = 0
    
    for md_file in md_files:
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查是否有 [[ 链接
            if '[[' not in content:
                skipped += 1
                continue
            
            new_content = convert_wikilinks(content, md_file, vault)
            
            if new_content != content:
                with open(md_file, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"  ✅ 已转换: {md_file.relative_to(vault)}")
                converted += 1
            else:
                skipped += 1
                
        except Exception as e:
            print(f"  ❌ 失败: {md_file.relative_to(vault)} — {e}")
    
    print(f"\n📊 转换完成: {converted} 个文件转换, {skipped} 个无需处理")
    print("💡 注意: 这是原地转换，会修改 vault 中的原始文件！")


def restore_from_git(vault_path: str):
    """如果启用了 git，可以恢复: git checkout -- *.md"""
    vault = Path(vault_path).expanduser()
    if (vault / '.git').exists():
        print("检测到 git 仓库，可用命令恢复: cd ~/Desktop/老H学金融 && git checkout -- '*.md'")
    else:
        print("没有 git 仓库，建议先提交或备份")


if __name__ == "__main__":
    vault = sys.argv[1] if len(sys.argv) > 1 else "~/Desktop/老H学金融"
    convert_vault(vault)
