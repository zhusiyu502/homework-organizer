#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
homework_organizer.py

需求1：扫描与列出文件（只读，不修改/删除任何文件）
    1. 接收目标文件夹路径作为命令行参数
    2. 遍历该文件夹内的所有文件（不递归进入子文件夹）
    3. 输出格式化表格：文件名 | 文件大小(KB) | 文件修改时间
    4. 支持可选参数过滤文件后缀，例如只扫描 .docx,.pdf

需求2：按文件类型自动归档（--organize）
    1. 读取目标目录文件，按后缀分类，移动到 图片/文档/视频/其他 文件夹
       - 图片：jpg, jpeg, png, gif, bmp
       - 文档：pdf, docx, doc, txt, xlsx
       - 视频：mp4, mov, avi
       - 其余后缀 -> 其他
    2. 只移动文件，不移动子文件夹；分类文件夹不存在则自动创建
    3. --dry-run 模拟移动，只打印操作，不真正改动文件（安全预览）
    4. 复用需求1的 collect_files() 扫描逻辑，不重复写扫描代码
    5. 真正执行前给出警告并二次确认

PR2 增强：
    6. 归档结束（含 dry-run）后，输出各分类文件数量汇总，便于核对结果
    7. 支持与 --ext 组合，只归档指定后缀的文件
    8. 同名文件自动追加序号，绝不覆盖已有文件
    9. 提供标准库 unittest 单元测试（test_homework_organizer.py）

需求3：批量改名（--rename）
    1. 改名规则：把「学号_姓名_作业名.ext」改为「作业名_学号.ext」
       例如：20230001_张三_数学作业.pdf -> 数学作业_20230001.pdf
    2. 强制流程：先打印全部“旧名 -> 新名”预览，用户输入 y 后才执行真实改名
    3. 目标文件名已存在时直接跳过，禁止覆盖原有文件，并给出提示
    4. 复用需求1的 collect_files() 扫描逻辑，不重复写扫描代码
    5. 可与 --ext 组合，只对指定后缀的文件改名
    6. --dry-run 可只看改名预览而不执行

仅依赖 Python 标准库，兼容 Windows。

--------------------------------------------------------------------------
运行示例（在项目目录下执行）：

    # 1) 扫描当前目录下所有文件（需求1）
    python homework_organizer.py .

    # 2) 扫描指定文件夹（Windows 路径含空格时用引号包裹）
    python homework_organizer.py "C:\\Users\\ENJOY\\Documents\\作业"

    # 3) 只扫描 .docx 和 .pdf 文件
    python homework_organizer.py . --ext .docx,.pdf
    python homework_organizer.py . -e docx,pdf        # 前缀点可省略

    # 4) 先模拟归档，安全预览将发生的移动（强烈推荐）
    python homework_organizer.py "D:\\作业" --organize --dry-run

    # 5) 确认无误后真正执行归档（执行前会二次确认）
    python homework_organizer.py "D:\\作业" --organize

    # 6) 只归档指定后缀（与 --ext 组合使用）
    python homework_organizer.py "D:\\作业" --organize -e pdf,docx --dry-run

    # 7) 批量改名：先打印“旧名 -> 新名”预览，按提示输入 y 才真正执行
    python homework_organizer.py "D:\\作业" --rename

    # 8) 仅查看改名预览，不执行改名
    python homework_organizer.py "D:\\作业" --rename --dry-run

    # 9) 只对指定后缀的文件改名
    python homework_organizer.py "D:\\作业" --rename -e pdf

    # 10) 运行单元测试（标准库 unittest，无需第三方依赖）
    python -m unittest -v

    # 11) 查看帮助
    python homework_organizer.py -h
--------------------------------------------------------------------------
"""

import argparse
import os
import shutil
import sys
from datetime import datetime


# ---------------------------------------------------------------------------
# 需求2：归档分类规则
# ---------------------------------------------------------------------------
# key 为分类文件夹名，value 为该分类包含的文件后缀（统一小写、带前导点）
CATEGORY_RULES = {
    "图片": {".jpg", ".jpeg", ".png", ".gif", ".bmp"},
    "文档": {".pdf", ".docx", ".doc", ".txt", ".xlsx"},
    "视频": {".mp4", ".mov", ".avi"},
}
# 未命中任何规则的后缀统一归入此分类
DEFAULT_CATEGORY = "其他"
# 汇总输出时使用的固定分类顺序（图片 -> 文档 -> 视频 -> 其他）
CATEGORY_ORDER = list(CATEGORY_RULES.keys()) + [DEFAULT_CATEGORY]


def parse_extensions(raw: str):
    """
    解析后缀过滤参数。

    参数:
        raw: 形如 ".docx,.pdf" 或 "docx,pdf" 的字符串；为空则返回 None。

    返回:
        set[str] | None: 全部转为小写、带前导点的小写后缀集合；
                         未提供时返回 None（表示不过滤）。
    """
    if raw is None:
        return None
    exts = set()
    for part in raw.split(","):
        part = part.strip().lower()
        if not part:
            continue
        # 统一补上前导点，便于和 os.path.splitext 的结果比较
        if not part.startswith("."):
            part = "." + part
        exts.add(part)
    # 若用户只输入了逗号/空格，视为未提供过滤
    return exts if exts else None


def human_readable_size(size_bytes: int, unit: str = "KB") -> str:
    """
    将字节数转换为指定单位（默认 KB）并格式化。

    参数:
        size_bytes: 文件字节数。
        unit: 目标单位，支持 "KB"、"MB"、"B"。

    返回:
        保留两位小数的字符串，例如 "12.34"。
    """
    if unit == "KB":
        value = size_bytes / 1024.0
    elif unit == "MB":
        value = size_bytes / (1024.0 * 1024.0)
    else:  # B
        value = float(size_bytes)
    return f"{value:.2f}"


def collect_files(target_dir: str, exts=None):
    """
    收集目标目录下的文件信息（不递归子文件夹）。

    参数:
        target_dir: 目标文件夹路径。
        exts: 后缀过滤集合（均为带点小写，如 {'.docx', '.pdf'}），None 表示不过滤。

    返回:
        list[dict]: 每项包含 name / size / mtime 的字典列表；
                    无论如何都不会修改或删除文件。
    """
    results = []
    # os.scandir 比 os.listdir 更高效，且能直接拿到 stat 信息
    with os.scandir(target_dir) as entries:
        for entry in entries:
            # 只处理“文件”，跳过子目录和其他类型（符号链接等由 is_file 判定）
            if not entry.is_file():
                continue

            # 后缀过滤：os.path.splitext 得到 (主名, '.ext')
            if exts is not None:
                _, suffix = os.path.splitext(entry.name)
                if suffix.lower() not in exts:
                    continue

            stat = entry.stat()  # 只读取元数据，不修改文件
            results.append(
                {
                    "name": entry.name,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                }
            )

    # 按文件名排序，输出更稳定、便于阅读
    results.sort(key=lambda item: item["name"].lower())
    return results


def print_table(files, target_dir: str):
    """
    以格式化表格输出文件清单。

    参数:
        files: collect_files 返回的结果列表。
        target_dir: 目标文件夹路径（仅用于显示）。
    """
    # 表头
    headers = ("文件名", "文件大小(KB)", "文件修改时间")

    # 若没有文件，直接提示
    if not files:
        print(f"文件夹中没有符合条件的文件：{os.path.abspath(target_dir)}")
        return

    # 预先计算每列宽度，保证表格对齐
    # 列宽 = max(表头宽度, 各单元格宽度) + 左右各一个空格
    name_w = max(len(headers[0]), max(len(f["name"]) for f in files))
    size_w = max(len(headers[1]), len("0.00"))
    # 修改时间统一格式化为 "YYYY-MM-DD HH:MM:SS"，宽度固定
    time_w = len(headers[2])

    # 让第三列至少能容纳表头宽度
    size_w = max(size_w, len(headers[1]))

    # 构造分隔线
    width = name_w + size_w + time_w + 4  # 4 为两个 '|' 及两侧空格
    separator = "-" * width

    # 打印标题信息
    print(f"扫描目录：{os.path.abspath(target_dir)}")
    print(f"共找到 {len(files)} 个文件")
    print(separator)

    # 表头行
    print(
        f"{headers[0]:<{name_w}} | "
        f"{headers[1]:>{size_w}} | "
        f"{headers[2]:<{time_w}}"
    )
    print(separator)

    # 数据行
    for item in files:
        size_kb = human_readable_size(item["size"], unit="KB")
        mtime = datetime.fromtimestamp(item["mtime"]).strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"{item['name']:<{name_w}} | "
            f"{size_kb:>{size_w}} | "
            f"{mtime:<{time_w}}"
        )

    print(separator)


# ---------------------------------------------------------------------------
# 需求2：按文件类型自动归档
# ---------------------------------------------------------------------------
def classify_file(filename: str) -> str:
    """
    根据文件名后缀判断归档分类。

    参数:
        filename: 文件名（如 "photo.JPG"）。

    返回:
        分类文件夹名：图片 / 文档 / 视频 / 其他。
    """
    _, suffix = os.path.splitext(filename)
    suffix = suffix.lower()
    # 依次匹配各分类的后缀集合
    for category, exts in CATEGORY_RULES.items():
        if suffix in exts:
            return category
    return DEFAULT_CATEGORY


def build_unique_path(dest_dir: str, filename: str) -> str:
    """
    生成目标路径，若同名文件已存在则自动追加序号，避免覆盖已有文件。

    参数:
        dest_dir: 目标分类文件夹。
        filename: 原始文件名。

    返回:
        不冲突的完整目标路径，例如 "文档/report_1.docx"。
    """
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(dest_dir, filename)
    index = 1
    # 直到找到一个磁盘上不存在的路径为止
    while os.path.exists(candidate):
        candidate = os.path.join(dest_dir, f"{base}_{index}{ext}")
        index += 1
    return candidate


def format_category_summary(category_counts: dict) -> str:
    """
    【PR2 增强】将各分类的文件数量格式化为多行文本。

    参数:
        category_counts: {分类名: 数量} 的字典。

    返回:
        形如 "  图片：2 个\n  文档：3 个" 的文本（按固定分类顺序排列）。
    """
    lines = []
    # 先按预设顺序输出已知分类，保证每次运行展示顺序一致
    for category in CATEGORY_ORDER:
        if category in category_counts:
            lines.append(f"  {category}：{category_counts[category]} 个")
    # 兜底：万一出现顺序表之外的分类，追加展示，避免遗漏
    for category, count in category_counts.items():
        if category not in CATEGORY_ORDER:
            lines.append(f"  {category}：{count} 个")
    return "\n".join(lines)


def organize_files(target_dir: str, files, dry_run: bool = False) -> int:
    """
    将 files 中的文件按类型移动到对应分类文件夹。

    参数:
        target_dir: 目标文件夹（文件所在的顶层目录）。
        files: 复用 collect_files() 得到的结果列表，每项含 name 字段。
        dry_run: 为 True 时只打印计划操作，不创建文件夹、不移动任何文件。

    返回:
        0 表示成功（或全部模拟成功），1 表示存在失败项。
    """
    # 第一步：先把移动计划计算出来（只读，不改动磁盘）
    plan = []  # 每项为 (分类, 源路径, 目标路径)
    category_counts = {}  # 【PR2 增强】统计每个分类包含的文件数量
    for item in files:
        name = item["name"]
        category = classify_file(name)
        src = os.path.join(target_dir, name)
        dest_dir = os.path.join(target_dir, category)
        dst = build_unique_path(dest_dir, name)
        plan.append((category, src, dst))
        category_counts[category] = category_counts.get(category, 0) + 1

    if not plan:
        print("没有需要归档的文件。")
        return 0

    # 打印模式标题
    if dry_run:
        print("=== 模拟运行（--dry-run）：以下操作不会真正执行 ===")
    else:
        print("=== 开始归档 ===")

    moved = 0
    failed = 0
    created_dirs = set()  # 记录本次已处理的分类文件夹，避免重复创建/提示

    for category, src, dst in plan:
        dest_dir = os.path.dirname(dst)
        # 分类文件夹不存在时创建（dry-run 下只提示，不创建）
        if dest_dir not in created_dirs and not os.path.isdir(dest_dir):
            if dry_run:
                print(f"[DRY-RUN] 将创建文件夹：{category}/")
            else:
                try:
                    os.makedirs(dest_dir, exist_ok=True)
                except OSError as exc:
                    print(f"[失败] 无法创建文件夹 {category}/：{exc}", file=sys.stderr)
                    failed += 1
                    continue
            created_dirs.add(dest_dir)

        # 执行移动（dry-run 下只打印）
        try:
            if not dry_run:
                shutil.move(src, dst)  # 仅移动，不删除源以外内容
            tag = "DRY-RUN" if dry_run else "OK"
            verb = "将移动" if dry_run else "已移动"
            print(f"[{tag}] {verb}：{os.path.basename(src)} -> {category}/")
            moved += 1
        except OSError as exc:
            print(f"[失败] {os.path.basename(src)}：{exc}", file=sys.stderr)
            failed += 1

    if dry_run:
        print(f"模拟完成：预计移动 {moved} 个文件"
              + (f"，其中 {failed} 个存在异常" if failed else ""))
    else:
        print(f"归档完成：成功 {moved} 个"
              + (f"，失败 {failed} 个" if failed else ""))

    # 【PR2 增强】输出各分类数量汇总，方便快速核对归档结果
    if category_counts:
        print("分类汇总：")
        print(format_category_summary(category_counts))

    return 0 if failed == 0 else 1


# ---------------------------------------------------------------------------
# 需求3：批量改名
# ---------------------------------------------------------------------------
# 改名规则：原始格式「学号_姓名_作业名.ext」 -> 目标格式「作业名_学号.ext」
# 例如：20230001_张三_数学作业.pdf -> 数学作业_20230001.pdf
RENAME_SEPARATOR = "_"


def build_renamed_name(filename: str):
    """
    根据改名规则计算新文件名。

    规则（以下划线分段）：
        学号   = 第 1 段
        姓名   = 第 2 段（改名后丢弃）
        作业名 = 第 3 段及之后的所有段（保留作业名中可能包含的下划线）

    参数:
        filename: 原始文件名，例如 "20230001_张三_数学作业.pdf"。

    返回:
        新文件名；若分段不足 3 段（不符合规则）则返回 None。
    """
    base, ext = os.path.splitext(filename)
    parts = base.split(RENAME_SEPARATOR)

    # 必须至少有 学号 / 姓名 / 作业名 三段，否则不处理
    if len(parts) < 3:
        return None

    student_id = parts[0]
    homework = RENAME_SEPARATOR.join(parts[2:])
    new_base = f"{homework}{RENAME_SEPARATOR}{student_id}"
    return new_base + ext


def plan_renames(files):
    """
    根据 collect_files() 的结果计算改名计划（只读，不改动磁盘）。

    冲突处理（禁止覆盖）：
        - 目标文件名与当前目录已有文件重名（大小写不敏感）-> 跳过
        - 多个源文件会改成同一个目标名 -> 只保留第一个，其余跳过
        - 新名称与原名称相同 -> 跳过

    参数:
        files: collect_files() 返回的列表，每项含 name 字段。

    返回:
        (renames, skipped)
            renames: list[tuple[str, str]]，元素为 (旧名, 新名)
            skipped: list[tuple[str, str]]，元素为 (文件名, 跳过原因)
    """
    # 已占用的文件名集合；normcase 使比较在 Windows 上大小写不敏感
    occupied = {os.path.normcase(f["name"]) for f in files}
    renames = []
    skipped = []

    for item in files:
        old = item["name"]
        new = build_renamed_name(old)

        if new is None:
            skipped.append((old, "不符合改名规则（需 学号_姓名_作业名.ext）"))
            continue
        if os.path.normcase(new) == os.path.normcase(old):
            skipped.append((old, "新名称与原名称相同"))
            continue
        # 目标名已被占用 -> 跳过，绝不覆盖
        if os.path.normcase(new) in occupied:
            skipped.append((old, f"目标文件名已存在，已跳过（不覆盖）：{new}"))
            continue

        renames.append((old, new))
        # 将新名称也标记为已占用，避免本次计划内两个文件改到同一目标名
        occupied.add(os.path.normcase(new))

    return renames, skipped


def print_rename_preview(target_dir: str, renames, skipped):
    """
    打印全部改名的“旧名 -> 新名”预览，以及被跳过的文件。

    本函数只读不写，不会修改任何文件。

    参数:
        target_dir: 目标文件夹（仅用于显示）。
        renames: 待改名列表 (旧名, 新名)。
        skipped: 被跳过的文件及原因。
    """
    print(f"改名目录：{os.path.abspath(target_dir)}")
    print(f"=== 改名预览（共 {len(renames)} 个文件将被重命名）===")

    if renames:
        # 计算列宽，保证预览对齐
        old_w = max(len("原文件名"), max(len(o) for o, _ in renames))
        new_w = max(len("新文件名"), max(len(n) for _, n in renames))
        print(f"{'原文件名':<{old_w}} -> {'新文件名':<{new_w}}")
        print("-" * (old_w + new_w + 4))
        for old, new in renames:
            print(f"{old:<{old_w}} -> {new:<{new_w}}")
    else:
        print("（没有可改名的文件）")

    if skipped:
        print(f"--- 已跳过 {len(skipped)} 个文件 ---")
        for name, reason in skipped:
            print(f"  [跳过] {name}：{reason}")


def apply_renames(target_dir: str, renames) -> int:
    """
    执行真正的改名操作（只在用户确认后调用，绝不覆盖已有文件）。

    参数:
        target_dir: 目标文件夹。
        renames: plan_renames() 得到的改名计划。

    返回:
        0 表示全部成功，1 表示存在跳过/失败项。
    """
    print("=== 开始改名 ===")
    ok = 0
    failed = 0

    for old, new in renames:
        src = os.path.join(target_dir, old)
        dst = os.path.join(target_dir, new)

        # 执行前再检查一次目标是否存在（双保险，防止预览到执行期间产生的新文件被覆盖）
        if os.path.exists(dst):
            print(f"[跳过] {old} -> {new}：目标已存在，不覆盖", file=sys.stderr)
            failed += 1
            continue

        try:
            os.rename(src, dst)
            print(f"[OK] {old} -> {new}")
            ok += 1
        except OSError as exc:
            print(f"[失败] {old} -> {new}：{exc}", file=sys.stderr)
            failed += 1

    print(f"改名完成：成功 {ok} 个" + (f"，跳过/失败 {failed} 个" if failed else ""))
    return 0 if failed == 0 else 1


def build_arg_parser():
    """构建命令行参数解析器（使用 argparse）。"""
    parser = argparse.ArgumentParser(
        prog="homework_organizer.py",
        description="扫描并列出指定文件夹内的文件（不递归子文件夹）；支持按类型自动归档、批量改名。",
        epilog="示例：python homework_organizer.py . --ext .docx,.pdf  |  "
               "python homework_organizer.py . --organize --dry-run  |  "
               "python homework_organizer.py . --rename",
    )
    # 位置参数：目标文件夹路径
    parser.add_argument(
        "folder",
        help="要扫描的目标文件夹路径，例如 . 或 \"C:\\\\Users\\\\ENJOY\\\\Documents\"",
    )
    # 可选参数：后缀过滤
    parser.add_argument(
        "-e",
        "--ext",
        metavar="EXT",
        default=None,
        help="可选：按后缀过滤，多个用逗号分隔，例如 .docx,.pdf（前缀点可省略）",
    )
    # 可选参数：归档模式（需求2）
    parser.add_argument(
        "--organize",
        action="store_true",
        help="归档模式：按类型把文件移动到 图片/文档/视频/其他 文件夹",
    )
    # 可选参数：模拟运行（需求2）
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="配合 --organize 或 --rename 使用：只预览操作，不真正改动文件",
    )
    # 可选参数：批量改名（需求3）
    parser.add_argument(
        "--rename",
        action="store_true",
        help="批量改名模式：把 学号_姓名_作业名.ext 改为 作业名_学号.ext（执行前预览并二次确认）",
    )
    return parser


def main(argv=None):
    """程序入口：解析参数 -> 校验目录 -> 收集文件 -> 列出或归档。"""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # --organize 与 --rename 是两种互斥的操作，不能同时使用
    if args.organize and args.rename:
        print("错误：--organize 与 --rename 不能同时使用。", file=sys.stderr)
        return 1

    target_dir = args.folder

    # 目录合法性校验（只读检查，不会创建或修改任何内容）
    if not os.path.exists(target_dir):
        print(f"错误：路径不存在 -> {target_dir}", file=sys.stderr)
        return 1
    if not os.path.isdir(target_dir):
        print(f"错误：路径不是文件夹 -> {target_dir}", file=sys.stderr)
        return 1

    # --dry-run 单独使用没有意义，给出提示（不视为错误）
    if args.dry_run and not (args.organize or args.rename):
        print("提示：--dry-run 需与 --organize 或 --rename 一起使用才有效。")

    exts = parse_extensions(args.ext)

    # 复用同一套扫描逻辑（需求1 的 collect_files）
    try:
        files = collect_files(target_dir, exts)
    except PermissionError:
        print(f"错误：没有权限读取该文件夹 -> {target_dir}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"错误：读取文件夹失败 -> {exc}", file=sys.stderr)
        return 1

    # ---- 需求3：批量改名 ----
    if args.rename:
        # 先计算改名计划（只读，不改动磁盘）
        renames, skipped = plan_renames(files)
        # 强制要求：先打印全部“旧名 -> 新名”预览
        print_rename_preview(target_dir, renames, skipped)

        if not renames:
            print("没有需要改名的文件，未做任何改动。")
            return 0

        # --dry-run：只看预览，不执行
        if args.dry_run:
            print("（--dry-run）仅预览改名结果，未做任何改动。")
            return 0

        # 强制二次确认：必须输入 y 才执行真实改名
        try:
            answer = input(
                "确认执行以上改名？输入 y 后回车执行，其他任意内容取消："
            ).strip().lower()
        except EOFError:
            print("无法读取确认输入，已取消，未做任何改动。")
            return 1
        if answer not in ("y", "yes"):
            print("已取消，未做任何改动。")
            return 0

        return apply_renames(target_dir, renames)

    # ---- 需求2：归档模式 ----
    if args.organize:
        # 安全预览：dry-run 不改变任何文件，无需确认
        if args.dry_run:
            return organize_files(target_dir, files, dry_run=True)

        # 警告提示 + 二次确认
        print("警告：即将按文件类型移动文件，这会改变文件的存放位置（不会删除文件）。")
        print(f"目标目录：{os.path.abspath(target_dir)}")
        try:
            answer = input("确认继续？输入 y 后回车执行，其他任意内容取消：").strip().lower()
        except EOFError:
            print("无法读取确认输入，已取消，未做任何改动。")
            return 1
        if answer not in ("y", "yes"):
            print("已取消，未做任何改动。")
            return 0

        return organize_files(target_dir, files, dry_run=False)

    # ---- 需求1：默认只列出 ----
    print_table(files, target_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
