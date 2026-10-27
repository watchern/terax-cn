# -*- coding: utf-8 -*-
"""生成 Teal-CN 品牌图标集(程序化绘制,圆角方块 + 终端提示符,各尺寸清晰)。
产出 assets/brand/:32x32.png, 128x128.png, 128x128@2x.png, icon.ico, icon.icns, logo.png
"""
from PIL import Image, ImageDraw

SIZE = 1024
TEAL_DARK = (13, 104, 97)
TEAL = (20, 184, 166)
BG_TOP = (24, 32, 38)
BG_BOTTOM = (10, 14, 17)
WHITE = (240, 253, 250)

img = Image.new('RGB', (SIZE, SIZE), BG_TOP)
draw = ImageDraw.Draw(img)
# 垂直渐变背景
for y in range(SIZE):
    t = y / (SIZE - 1)
    r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
    g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
    b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
    draw.line([(0, y), (SIZE, y)], fill=(r, g, b))

# 圆角青色描边内框
margin, radius, width = 84, 190, 26
draw.rounded_rectangle([margin, margin, SIZE - margin, SIZE - margin],
                       radius=radius, outline=TEAL, width=width)

# 终端提示符 ">"(两条粗线)与光标 "_"
lw = 72
cx, cy = 300, 400
arm = 150
draw.line([(cx, cy), (cx + arm, cy + arm)], fill=WHITE, width=lw)
draw.line([(cx + arm, cy + arm), (cx, cy + 2 * arm)], fill=WHITE, width=lw)
draw.rounded_rectangle([cx + arm + 110, cy + 2 * arm - 10, cx + arm + 110 + 300, cy + 2 * arm + lw - 10],
                       radius=18, fill=WHITE)

# 输出各尺寸
out = 'assets/brand'
import os
os.makedirs(out, exist_ok=True)
img.save(f'{out}/master-1024.png')


def save_px(size, name):
    img.resize((size, size), Image.LANCZOS).save(f'{out}/{name}')


save_px(32, '32x32.png')
save_px(128, '128x128.png')
save_px(256, '128x128@2x.png')
save_px(256, 'logo.png')
img.resize((256, 256), Image.LANCZOS).save(
    f'{out}/icon.ico', sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
icns_sizes = [16, 32, 64, 128, 256, 512, 1024]
imgs = [img.resize((s, s), Image.LANCZOS) for s in icns_sizes]
imgs[0].save(f'{out}/icon.icns', format='ICNS', append_images=imgs[1:])
for f in sorted(os.listdir(out)):
    print(f, os.path.getsize(f'{out}/{f}'))
