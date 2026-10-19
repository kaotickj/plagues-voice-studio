"""Convert the approved PNG logo into a Windows multi-resolution icon."""
from pathlib import Path
from PIL import Image

root = Path(__file__).resolve().parent / 'assets'
with Image.open(root / 'dj-writer.png') as image:
    image.convert('RGBA').save(root / 'dj-writer.ico', format='ICO',
                               sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
