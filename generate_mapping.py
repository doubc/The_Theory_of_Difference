# -*- coding: utf-8 -*-
"""
文件映射表生成器 - 为The_Theory_of_Difference项目生成Excel-ready CSV
"""
import os
import csv
from pathlib import Path

ROOT_DIR = r"D:\python work\The_Theory_of_Difference"

# 文件分类规则
CATEGORY_MAP = {
    "01-核心理论-差异论": "core-theory",
    "02-worldbase物理框架": "physics-framework",
    "03-worldbase化学理论": "chemistry",
    "04-社会科学应用": "social-science",
    "05-历史版本归档": "archive",
    "06-广义相对论的论证": "general-relativity",
    "calculations": "derivations",
    "logs": "explorations-logs",
    "papers": "papers",
    "framework": "framework",
}

# 大文件摘要模板（需手动填充）
LARGE_FILE_SUMMARIES = {
    "worldbase数学框架及全物理对应.md": "WorldBase核心文档：十公理体系、离散状态空间、连续极限定理、引力/电磁/弱力统一推导",
    "差异论V1.5.md": "差异论完整表述v1.5：九生成机制详细论证",
    "差异论V1.6.md": "差异论最新完整版v1.6：所有9机制严格论证+社会科学命题重写",
    "差异论V1.6EN.md": "差异论v1.6英文版",
    "worldbaseV2.1.md": "WorldBase v2.1最新版：精修后的公理化物理框架",
    "worldbase-v2.1-split/worldbaseV2.1-full.md": "WorldBase v2.1分章节完整版",
    "历史的公理分析_V1.3.md": "历史领域应用：周代/秦汉/唐宋/明清公理解读",
    "worldbaseV2.0.md": "WorldBase v2.0：昨天精修版本",
    "历史的公理分析_V1.4.md": "历史分析v1.4：全面工具箱版本",
    "worldbase本地完整化版本V1.9.md": "WorldBase本地化v1.9",
    "差异即世界V1.1.md": "本体论展开：'一切都是差异'的语法层链接",
    "worldbase本地完整化版本V1.8.md": "WorldBase本地化v1.8",
    "象界.md": "现象学维度：结构/主体在约束中的筛选与显现",
    "历史的公理分析_全书V1.0.md": "历史公理分析全书版",
    "worldbase本地完整化版本V1.6.md": "WorldBase本地化v1.6",
    "worldbase物理版全版V1.2.md": "WorldBase物理领域完整表述v1.2",
    "公理社会论文.md": "社会领域最长应用论文",
    "worldbase本地完整化版本.md": "WorldBase本地化早期版本",
    "worldbaseV1.3.md": "WorldBase v1.3早期版本",
}

def get_category(filepath):
    """根据路径确定分类"""
    rel_path = os.path.relpath(filepath, ROOT_DIR)
    for key, value in CATEGORY_MAP.items():
        if rel_path.startswith(key):
            return value
    return "unknown"

def suggest_english_name(filename, category):
    """基于文件名和类别建议英文名"""
    # 已有英文名的保持不变
    if filename.endswith("-en.md") or any(c.isdigit() for c in filename[:3]):
        return filename
    
    # papers目录特殊处理
    if category == "papers":
        return filename  # 已经是英文
    
    # framework目录
    if category == "framework":
        name_map = {
            "proof-status.md": "proof-status.md",
            "glossary.md": "glossary.md",
        }
        return name_map.get(filename, filename)
    
    # 其他目录的翻译映射
    translation_map = {
        # 核心理论
        "差异论导论.md": "01-introduction-to-difference-theory.md",
        "差异论V1.5.md": "difference-theory-v1.5.md",
        "差异论V1.6.md": "difference-theory-v1.6.md",
        "差异论V1.6EN.md": "difference-theory-v1.6-en.md",
        "差异即世界V1.1.md": "difference-is-world-v1.1.md",
        "象界.md": "phenomenal-realm.md",
        "象界形式化文档V0.8.md": "phenomenal-realm-formalization-v0.8.md",
        "Appearing Before Appearing_ A Structural Account of Pre-Phenomenal Manifestation.md": "appearing-before-appearing.md",
        "差异论未说出的可能社会结构 (2).md": "unstated-social-structures-v2.md",
        "差异论未说出的可能社会结构_减少公理版.md": "unstated-social-structures-reduced-axioms.md",
        
        # WorldBase物理
        "worldbase数学框架及全物理对应.md": "worldbase-mathematical-framework.md",
        "引力的论文.md": "gravity-paper.md",
        "引力的论文英文版.md": "gravity-paper-en.md",
        "引力约束条件的枚举.md": "gravity-constraints-enumeration.md",
        "弱力英文版V1.3.md": "weak-force-en-v1.3.md",
        "弱力英文版V1.4.md": "weak-force-en-v1.4.md",
        "d=2双守恒湍流论文.md": "turbulence-2d-double-conservation.md",
        
        # 化学
        "WolrdBase化学再定义版本V0.11.md": "chemistry-redefinition-v0.11.md",
        "WorldBase化学再定义版本V0.9.md": "chemistry-redefinition-v0.9.md",
        "worldbase_化学再定义_V0.13.md": "chemistry-redefinition-v0.13.md",
        "关于如何从物理1.2建立化学映射的思考.md": "physics-to-chemistry-mapping.md",
        
        # 社科
        "历史的公理分析_V1.3.md": "historical-axiomatic-analysis-v1.3.md",
        "历史的公理分析_V1.4.md": "historical-axiomatic-analysis-v1.4.md",
        "历史的公理分析_全书V1.0.md": "historical-axiomatic-analysis-complete-v1.0.md",
        "中国政治的公理解读.md": "china-politics-axiomatic-interpretation.md",
        "中美公理诊断.md": "china-us-axiomatic-diagnosis.md",
        "公理社会论文.md": "axiomatic-society-paper.md",
        
        # 计算笔记
        "Dirac方程.md": "dirac-equation.md",
        "泡利不相容原理.md": "pauli-exclusion-principle.md",
        "自旋推导.md": "spin-derivation.md",
        "宇宙常数.md": "cosmological-constant.md",
        
        # Logs
        "关于我们在做什么的思考.md": "reflection-on-our-work.md",
        "关于电荷定义唯一性问题的讨论.md": "charge-uniqueness-discussion.md",
    }
    
    return translation_map.get(filename, filename.replace(".md", ".md"))

def should_archive(filepath, category):
    """判断是否应归档"""
    rel_path = os.path.relpath(filepath, ROOT_DIR)
    
    # 已经在archive目录的
    if category == "archive":
        return True
    
    # 历史版本
    if "V1.3" in filepath or "V1.4" in filepath or "V1.5" in filepath:
        if "worldbase" in filepath.lower() and "papers" not in filepath:
            return True
    
    # 本地完整化版本的旧版
    if "本地完整化版本" in filepath and "V1.9" not in filepath:
        return True
    
    # V4.x-V5.0历史版本
    if "V4." in filepath or ("V5.0" in filepath and "全新修正版" not in filepath):
        return True
    
    return False

def get_priority(category, filename, filepath):
    """优先级标记"""
    # 高优先级：核心论文和框架文档
    if category in ["papers", "framework"]:
        return "HIGH"
    
    # 中优先级：当前版本的核心文档
    if "V1.6" in filename or "V2.1" in filename or "V2.0" in filename:
        if "历史版本归档" not in filepath:
            return "MEDIUM"
    
    # 低优先级：历史版本和探索性内容
    return "LOW"

def main():
    """主函数：扫描并生成CSV"""
    results = []
    
    for root, dirs, files in os.walk(ROOT_DIR):
        # 跳过.git目录
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for file in files:
            if not file.endswith('.md'):
                continue
            
            filepath = os.path.join(root, file)
            rel_path = os.path.relpath(filepath, ROOT_DIR)
            
            # 获取文件大小
            size = os.path.getsize(filepath)
            size_kb = size / 1024
            
            # 分类
            category = get_category(filepath)
            
            # 建议英文名
            english_name = suggest_english_name(file, category)
            
            # 是否归档
            archive = should_archive(filepath, category)
            
            # 优先级
            priority = get_priority(category, file, filepath)
            
            # 摘要（大文件）
            summary = LARGE_FILE_SUMMARIES.get(file, "")
            if not summary and size_kb > 50:
                summary = f"大型文档 ({size_kb:.0f}KB)，需人工摘要"
            
            results.append({
                "原文件名": file,
                "建议英文名": english_name,
                "相对路径": rel_path,
                "所属目录": category,
                "文件大小_KB": f"{size_kb:.1f}",
                "核心主题": "",  # 需人工填写
                "是否归档": "YES" if archive else "NO",
                "优先级": priority,
                "摘要": summary,
                "备注": "",
            })
    
    # 按优先级和大小排序
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    results.sort(key=lambda x: (priority_order.get(x["优先级"], 3), -float(x["文件大小_KB"])))
    
    # 写入CSV
    output_file = os.path.join(ROOT_DIR, "file_mapping.csv")
    fieldnames = ["原文件名", "建议英文名", "相对路径", "所属目录", "文件大小_KB", 
                  "核心主题", "是否归档", "优先级", "摘要", "备注"]
    
    with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"✅ 文件映射表已生成: {output_file}")
    print(f"📊 总计 {len(results)} 个Markdown文件")
    print(f"\n优先级分布:")
    from collections import Counter
    priority_counts = Counter(r["优先级"] for r in results)
    for p in ["HIGH", "MEDIUM", "LOW"]:
        print(f"  {p}: {priority_counts.get(p, 0)} 个文件")
    
    archive_count = sum(1 for r in results if r["是否归档"] == "YES")
    print(f"  建议归档: {archive_count} 个文件")

if __name__ == "__main__":
    main()
