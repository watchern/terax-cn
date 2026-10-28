# -*- coding: utf-8 -*-
"""生成 Teal-CN 品牌图标集(RGBA,透明背景圆角方块 + 终端提示符)。
产出 assets/brand/:32x32.png, 128x128.png, 128x128@2x.png, icon.ico, icon.icns, logo.png
注意:Tauri 的 generate_context! 宏强制要求 PNG 为 RGBA,本脚本产出并自检 alpha 通道。
"""
from PIL import Image, ImageDraw

S = 2048          # 超采样画布,缩小后边缘平滑
OUT = 1024
TEAL = (20, 184, 166)
BG_TOP = (24, 32, 38)
BG_BOTTOM = (10, 14, 17)
WHITE = (240, 253, 250)

# 背景垂直渐变(RGB 层,稍后经圆角蒙版合成)
grad = Image.new('RGB', (S, S))
gd = ImageDraw.Draw(grad)
for y in range(S):
    t = y / (S - 1)
    gd.line([(0, y), (S, y)], fill=tuple(
        int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3)))

# 圆角蒙版(透明背景 + 圆角方块区域)
mask = Image.new('L', (S, S), 0)
md = ImageDraw.Draw(mask)
margin, radius = 96, 400
md.rounded_rectangle([margin, margin, S - margin, S - margin], radius=radius, fill=255)

body = Image.new('RGBA', (S, S), (0, 0, 0, 0))
body.paste(grad, (0, 0), mask)

# 内容层:白色终端提示符 ">_"(按蒙版裁剪,避免出界)
overlay = Image.new('RGBA', (S, S), (0, 0, 0, 0))
od = ImageDraw.Draw(overlay)
lw = 150
cx, cy, arm = 620, 700, 320
od.line([(cx, cy), (cx + arm, cy + arm)], fill=WHITE + (255,), width=lw)
od.line([(cx + arm, cy + arm), (cx, cy + 2 * arm)], fill=WHITE + (255,), width=lw)
od.rounded_rectangle([cx + arm + 230, cy + 2 * arm - 20, cx + arm + 230 + 640, cy + 2 * arm + lw - 20],
                     radius=40, fill=WHITE + (255,))
overlay.putalpha(Image.composite(overlay.getchannel('A'), Image.new('L', (S, S), 0), mask))

img = Image.alpha_composite(body, overlay).resize((OUT, OUT), Image.LANCZOS)

out = 'assets/brand'
import os
os.makedirs(out, exist_ok=True)
img.save(f'{out}/master-1024.png')


def save_px(size, name):
    im = img.resize((size, size), Image.LANCZOS)
    assert im.mode == 'RGBA'
    im.save(f'{out}/{name}')


save_px(32, '32x32.png')
save_px(128, '128x128.png')
save_px(256, '128x128@2x.png')
save_px(256, 'logo.png')
ico = img.resize((256, 256), Image.LANCZOS)
ico.save(f'{out}/icon.ico', sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
icns_sizes = [16, 32, 64, 128, 256, 512, 1024]
imgs = [img.resize((s, s), Image.LANCZOS) for s in icns_sizes]
imgs[0].save(f'{out}/icon.icns', format='ICNS', append_images=imgs[1:])

# 自检:所有 PNG 必须为 RGBA(color type 6),否则 Tauri 宏会 panic
def png_color_type(p):
    with open(p, 'rb') as f:
        return f.read(26)[25]


for f in ['32x32.png', '128x128.png', '128x128@2x.png', 'logo.png', 'master-1024.png']:
    ct = png_color_type(f'{out}/{f}')
    assert ct == 6, f'{f} 不是 RGBA (color type={ct})'
print('OK: 全部 PNG 为 RGBA')
for f in sorted(os.listdir(out)):
    print(f, os.path.getsize(f'{out}/{f}'))
