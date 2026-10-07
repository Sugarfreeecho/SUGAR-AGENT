"""生成桌面版图标资源：assets/app.ico（多尺寸）与 assets/tray.ico。"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
PACKAGING = HERE.parent
REPO = PACKAGING.parent
ASSETS = PACKAGING / "assets"
LOGO = REPO / "app" / "assets" / "sugar-logo.png"
TRAY = REPO / "app" / "assets" / "sugar_tray.ico"


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    if not LOGO.is_file():
        print(f"缺少图标源文件：{LOGO}", file=sys.stderr)
        return 1

    image = Image.open(LOGO).convert("RGBA")
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    target = ASSETS / "app.ico"
    image.save(target, format="ICO", sizes=sizes)
    print(f"已生成应用图标：{target}（{image.width}x{image.height} → {len(sizes)} 个尺寸）")

    if TRAY.is_file():
        shutil.copyfile(TRAY, ASSETS / "tray.ico")
        print(f"已复制托盘图标：{ASSETS / 'tray.ico'}")
    else:
        image.resize((32, 32), Image.LANCZOS).save(ASSETS / "tray.ico", format="ICO", sizes=[(32, 32), (16, 16)])
        print(f"已生成托盘图标（回退）：{ASSETS / 'tray.ico'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
