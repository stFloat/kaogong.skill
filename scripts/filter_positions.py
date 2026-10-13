"""公务员职位表快速筛选脚本（零第三方依赖，仅用 Python 标准库）

用法示例：
  python filter_positions.py 职位表.csv --专业 "计算机" --学历 "本科" --政治面貌 "中共党员"
  python filter_positions.py 职位表.csv --基层 "2年" --招录 "2以上" --备注排除 "五年服务期"

行为说明：
  - 自动识别常见列名（兼容国考/京考/事业单位职位表的不同表头写法）
  - 组合条件为 AND 关系；条件值为模糊包含匹配（不区分英文大小写）
  - "--备注排除"用半角分号分隔多个关键词，命中任一即剔除该岗位
  - 输出筛选结果到 stdout，并同时写一份 filter_result.csv

退出码：
  0 = 正常完成；1 = 职位表打开失败或无有效数据；2 = 未识别到任何条件列。
"""

import argparse
import csv
import re
import sys

# (逻辑字段, 别名列表[匹配时去空格、小写化])
COLUMN_ALIASES = {
    "专业": ["专业", "专业要求", "专业名称", "招聘专业", "职位专业"],
    "学历": ["学历", "学历要求", "学历最低要求"],
    "学位": ["学位", "学位要求"],
    "政治面貌": ["政治面貌"],
    "基层": ["基层工作最低年限", "基层工作经历", "基层工作年限", "最低基层工作年限"],
    "基层服务项目": ["服务基层项目工作经历", "服务基层项目经历"],
    "户籍": ["户籍要求", "户籍"],
    "应届": ["应届"],
    "招录": ["招考人数", "招录人数", "招聘人数", "计划招录人数", "拟招录人数"],
    "备注": ["备注", "职位备注", "其他条件"],
}


def normalize(value):
    """去空白 + 小写，用于列名与关键字匹配。"""
    return re.sub(r"[\s\u3000]", "", value).lower()


def find_column(header, logical):
    """根据逻辑字段在表头中定位实际列名（索引）。找不到返回 None。"""
    normalized_header = {idx: normalize(col) for idx, col in enumerate(header)}
    for alias in COLUMN_ALIASES.get(logical, []):
        target = normalize(alias)
        for idx, col in normalized_header.items():
            if col == target or target in col:
                return idx
    return None


def parse_args():
    parser = argparse.ArgumentParser(
        description="公务员职位表硬条件筛选（模糊包含匹配，组合为 AND）"
    )
    parser.add_argument("csv_path", help="官方职位表 CSV 文件路径（建议 UTF-8 编码）")
    for logical in COLUMN_ALIASES:
        parser.add_argument(
            f"--{logical}", default=None,
            help=f"按「{logical}」列过滤：{ ' / '.join(COLUMN_ALIASES[logical]) }"
        )
    parser.add_argument(
        "--备注排除",
        default=None,
        help="半角分号分隔，如：'五年服务期;二次分配;适合男性'，命中任一即剔除",
    )
    return parser.parse_args()


def read_table(csv_path):
    """读取 CSV，返回 (header, rows)。兼容 UTF-8 / GBK / UTF-8-BOM。"""
    for encoding in ("utf-8-sig", "gbk", "utf-8"):
        try:
            with open(csv_path, "r", encoding=encoding, newline="") as f:
                reader = csv.reader(f)
                header = next(reader)
                rows = [row for row in reader]
            return header, rows
        except (UnicodeDecodeError, StopIteration):
            continue
    raise ValueError(f"无法读取职位表文件: {csv_path}")


def main():
    args = parse_args()

    try:
        header, rows = read_table(args.csv_path)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

    header = [h.strip() for h in header]
    logical_cols = [logical for logical in COLUMN_ALIASES if getattr(args, logical)]
    if not logical_cols and not args.备注排除:
        print(
            "错误：没有指定任何过滤条件。\n"
            "用法示例：python filter_positions.py 职位表.csv --专业 计算机 --学历 本科",
            file=sys.stderr,
        )
        return 2

    # 解析列位置
    col_index = {}
    for logical in logical_cols:
        idx = find_column(header, logical)
        if idx is None:
            print(
                f"警告：未在表头中找到「{logical}」对应列，跳过该条件。"
                f"现有列：{', '.join(header)}",
                file=sys.stderr,
            )
            continue
        col_index[logical] = idx

    exclude_idx = find_column(header, "备注") if args.备注排除 else None
    if args.备注排除 and exclude_idx is None:
        print("警告：未找到备注列，跳过排除条件。", file=sys.stderr)

    matched = []
    for row in rows:
        # 行长度补齐，避免缺列越界
        if len(row) < len(header):
            row = row + [""] * (len(header) - len(row))

        ok = True
        for logical, idx in col_index.items():
            cell = normalize(row[idx])
            keyword = normalize(getattr(args, logical))
            if keyword and keyword not in cell:
                ok = False
                break
        if not ok:
            continue

        # 备注排除检查
        if exclude_idx is not None:
            note = normalize(row[exclude_idx])
            for banned in args.备注排除.split(";"):
                if banned and normalize(banned) in note:
                    ok = False
                    break
        if ok:
            matched.append(row)

    # 输出
    print(f"表头列：{', '.join(header)}")
    print(f"原始岗位数：{len(rows)}  筛选命中：{len(matched)}\n")
    for row in matched:
        print(" | ".join(row))
        print("-" * 60)

    if matched:
        with open("filter_result.csv", "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(matched)
        print(f"\n已写入 filter_result.csv（共 {len(matched)} 条）")

    return 0


if __name__ == "__main__":
    sys.exit(main())