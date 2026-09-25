from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pages_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--columns", type=int, default=3)
    parser.add_argument("--rows", type=int, default=3)
    args = parser.parse_args()

    pages = sorted(args.pages_dir.glob("*.png"), key=lambda path: int(path.stem.rsplit("-", 1)[1]))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    thumb_width, thumb_height, label_height = 420, 594, 24
    per_sheet = args.columns * args.rows
    for sheet_index in range(0, len(pages), per_sheet):
        subset = pages[sheet_index:sheet_index + per_sheet]
        canvas = Image.new(
            "RGB",
            (args.columns * thumb_width, args.rows * (thumb_height + label_height)),
            "#d7d7d7",
        )
        draw = ImageDraw.Draw(canvas)
        for slot, path in enumerate(subset):
            page = Image.open(path).convert("RGB")
            page.thumbnail((thumb_width - 8, thumb_height - 8))
            column, row = slot % args.columns, slot // args.columns
            x = column * thumb_width + (thumb_width - page.width) // 2
            y = row * (thumb_height + label_height) + label_height
            draw.text((column * thumb_width + 8, row * (thumb_height + label_height) + 4), path.stem, fill="black")
            canvas.paste(page, (x, y))
        output = args.output_dir / f"contact-{sheet_index // per_sheet + 1:02d}.jpg"
        canvas.save(output, quality=88, optimize=True)


if __name__ == "__main__":
    main()
