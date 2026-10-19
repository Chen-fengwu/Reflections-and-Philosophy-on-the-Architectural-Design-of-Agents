#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stamp_prediction.py — 为趋势分析假设生成带时间戳的预测记录。

确定性地把一条可证伪假设写入本地 JSON 文件，附带 UTC 时间戳与唯一 ID。
不调用任何模型，不联网，仅使用 Python 标准库。

用法:
    python scripts/stamp_prediction.py \
        --hypothesis "由于算力成本下降，未来6个月内，端侧AI设备月出货量出现两位数增长" \
        --metrics "端侧出货量, 整机均价, 相关应用上线数" \
        --window "6m"

输出:
    默认写入同目录下的 predictions.json（JSON 数组，逐条追加）。
    同时在 stdout 打印本次新增的记录，在 stderr 打印累计条数。

退出码:
    0  成功
    1  写入失败
    2  参数校验失败（由 argparse 触发）
    3  已有文件损坏或格式不符
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone

SCHEMA_VERSION = "1.0"
DEFAULT_OUT = "predictions.json"


def parse_metrics(raw: str) -> list[str]:
    """把逗号或分号分隔的指标字符串解析为去重后保持顺序的列表。"""
    items: list[str] = []
    for chunk in raw.replace(";", ",").split(","):
        item = chunk.strip()
        if item:
            items.append(item)
    return items


def build_record(hypothesis: str, metrics: list[str], window: str) -> dict:
    """构造一条记录，包含唯一 ID 与 UTC 时间戳。"""
    return {
        "schema_version": SCHEMA_VERSION,
        "id": str(uuid.uuid4()),
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "hypothesis": hypothesis,
        "metrics": metrics,
        "window": window,
    }


def load_existing(path: str) -> list:
    """读取已有记录文件；文件不存在则返回空列表。"""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"error: 无法读取已有文件 {path}: {exc}\n")
        raise SystemExit(3)
    if not isinstance(data, list):
        sys.stderr.write(f"error: {path} 的内容不是 JSON 数组，拒绝覆盖\n")
        raise SystemExit(3)
    return data


def atomic_write(path: str, records: list) -> None:
    """先写临时文件再原子替换，避免中断导致文件损坏。"""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(records, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="stamp_prediction.py",
        description="记录一条趋势分析假设，写入带 UTC 时间戳与唯一 ID 的本地 JSON 文件。",
        epilog=(
            "示例:\n"
            "  python scripts/stamp_prediction.py \\\n"
            '    --hypothesis "由于算力成本下降，未来6个月内，端侧AI设备月出货量出现两位数增长" \\\n'
            '    --metrics "端侧出货量, 整机均价, 相关应用上线数" \\\n'
            '    --window "6m"'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--hypothesis", required=True,
        help="可证伪的假设全文（必须包含时间窗口与证伪条件）",
    )
    parser.add_argument(
        "--metrics", required=True,
        help="可观测指标，逗号或分号分隔，例如 \"指标A, 指标B, 指标C\"",
    )
    parser.add_argument(
        "--window", required=True,
        help="时间窗口，例如 6m / 12m / 2026-Q2 / 2026-04",
    )
    parser.add_argument(
        "--out", default=DEFAULT_OUT,
        help=f"输出 JSON 文件路径（默认 {DEFAULT_OUT}）",
    )
    args = parser.parse_args(argv)

    hypothesis = (args.hypothesis or "").strip()
    metrics = parse_metrics(args.metrics or "")
    window = (args.window or "").strip()

    if not hypothesis:
        parser.error("--hypothesis 不能为空")
    if len(metrics) < 1:
        parser.error("--metrics 至少需要一个可观测指标")
    if not window:
        parser.error("--window 不能为空")

    record = build_record(hypothesis, metrics, window)
    records = load_existing(args.out)
    records.append(record)

    try:
        atomic_write(args.out, records)
    except OSError as exc:
        sys.stderr.write(f"error: 写入 {args.out} 失败: {exc}\n")
        return 1

    sys.stdout.write(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    sys.stderr.write(f"已写入 {args.out}（当前共 {len(records)} 条记录）\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
