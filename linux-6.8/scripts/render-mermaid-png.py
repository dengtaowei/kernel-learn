#!/usr/bin/env python3
"""
从 Markdown 提取 ```mermaid 代码块，经 Kroki 渲染为 PNG。

依赖：Python 3.6+、可访问 https://kroki.io（无需 npm/mermaid-cli）

用法示例：
  # 本仓库默认：渲染 stm32 / usb 两篇文档到 pics/
  ./scripts/render-mermaid-png.py

  # 任意单个 md，自动命名：<stem>-01.png, <stem>-02.png, ...
  ./scripts/render-mermaid-png.py docs/foo.md

  # 指定输出目录与文件名前缀
  ./scripts/render-mermaid-png.py foo.md -o pics -p mydiagram

  # 自定义每个 PNG 的文件名（逗号分隔，数量需与图块数一致）
  ./scripts/render-mermaid-png.py foo.md -o pics -n fig-a,fig-b,fig-c

  # 只导出 .mmd 源文件，不请求网络
  ./scripts/render-mermaid-png.py foo.md --mmd-only -o pics
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

KROKI_URL = "https://kroki.io/mermaid/png"

# 无参数时的默认任务（本仓库）
DEFAULT_JOBS = [
    (
        "stm32-pinctrl-analysis.md",
        [
            "stm32-pinctrl-01-three-phase-flowchart",
            "stm32-pinctrl-02-sequence",
            "stm32-pinctrl-03-pinmux-parse",
            "stm32-pinctrl-04-map-to-setting",
            "stm32-pinctrl-05-set-mux-hardware",
        ],
    ),
    (
        "usb-enumeration-and-probe.md",
        [
            "usb-enumeration-01-four-layer-flowchart",
            "usb-enumeration-02-probe-sequence",
            "usb-enumeration-03-match-flowchart",
        ],
    ),
]


def extract_mermaid_blocks(text: str) -> list[str]:
    pattern = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
    return [m.group(1).strip() for m in pattern.finditer(text)]


def render_png(mermaid_src: str, out_path: Path, kroki_url: str = KROKI_URL) -> None:
    req = urllib.request.Request(
        kroki_url,
        data=mermaid_src.encode("utf-8"),
        headers={
            "Content-Type": "text/plain",
            "User-Agent": "mermaid-png-render/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        png = resp.read()
    if png[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"response is not PNG: {out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(png)


def default_names(stem: str, count: int, prefix: str | None = None) -> list[str]:
    p = prefix or stem
    return [f"{p}-{i:02d}" for i in range(1, count + 1)]


def process_file(
    md_path: Path,
    out_dir: Path,
    names: list[str] | None,
    prefix: str | None,
    mmd_only: bool,
    kroki_url: str,
) -> int:
    if not md_path.is_file():
        print(f"error: not found: {md_path}", file=sys.stderr)
        return 1

    blocks = extract_mermaid_blocks(md_path.read_text(encoding="utf-8"))
    if not blocks:
        print(f"warn: no mermaid blocks in {md_path}", file=sys.stderr)
        return 0

    stem = md_path.stem
    if names is None:
        names = default_names(stem, len(blocks), prefix)
    elif len(names) != len(blocks):
        print(
            f"error: {len(names)} names but {len(blocks)} mermaid blocks in {md_path}",
            file=sys.stderr,
        )
        return 1

    for i, (block, base) in enumerate(zip(blocks, names)):
        mmd_path = out_dir / f"{base}.mmd"
        png_path = out_dir / f"{base}.png"
        mmd_path.write_text(block + "\n", encoding="utf-8")
        print(f"[{i + 1}/{len(blocks)}] {base}.mmd")
        if mmd_only:
            continue
        print(f"       -> {png_path.name} ...", end=" ", flush=True)
        try:
            render_png(block, png_path, kroki_url)
            print(f"ok ({png_path.stat().st_size} bytes)")
        except urllib.error.URLError as e:
            print(f"fail: {e}", file=sys.stderr)
            return 1
    return 0


def run_defaults(root: Path, out_dir: Path, mmd_only: bool, kroki_url: str) -> int:
    rc = 0
    for md_name, names in DEFAULT_JOBS:
        md_path = root / md_name
        r = process_file(md_path, out_dir, names, None, mmd_only, kroki_url)
        if r:
            rc = r
    return rc


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Extract mermaid from Markdown and render PNG via Kroki.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "markdown",
        nargs="*",
        help="Markdown file(s). Omit to run built-in jobs for this repo.",
    )
    p.add_argument(
        "-o", "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: <repo>/pics or cwd/pics)",
    )
    p.add_argument(
        "-p", "--prefix",
        help="Filename prefix when auto-naming (default: md file stem)",
    )
    p.add_argument(
        "-n", "--names",
        help="Comma-separated PNG basenames (no .png), one per mermaid block",
    )
    p.add_argument(
        "--mmd-only",
        action="store_true",
        help="Only write .mmd sources, skip Kroki PNG rendering",
    )
    p.add_argument(
        "--kroki-url",
        default=KROKI_URL,
        help=f"Kroki endpoint (default: {KROKI_URL})",
    )
    p.add_argument(
        "-r", "--root",
        type=Path,
        default=None,
        help="Repo root for default jobs (default: parent of scripts/)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    script_dir = Path(__file__).resolve().parent
    root = (args.root or script_dir.parent).resolve()
    out_dir = (args.output_dir or root / "pics").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.markdown:
        return run_defaults(root, out_dir, args.mmd_only, args.kroki_url)

    names_list = None
    if args.names:
        names_list = [s.strip() for s in args.names.split(",") if s.strip()]
        if len(args.markdown) > 1:
            print("error: -n only valid with a single markdown file", file=sys.stderr)
            return 1

    rc = 0
    for md in args.markdown:
        md_path = Path(md)
        if not md_path.is_absolute():
            md_path = Path.cwd() / md_path
        md_path = md_path.resolve()
        n = names_list if len(args.markdown) == 1 else None
        r = process_file(
            md_path, out_dir, n, args.prefix, args.mmd_only, args.kroki_url
        )
        if r:
            rc = r
    return rc


if __name__ == "__main__":
    sys.exit(main())
