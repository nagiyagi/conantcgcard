"""Generate PNG icons for the PWA from scratch (no SVG dependency)."""
from PIL import Image, ImageDraw, ImageFont
import os

BG = (13, 17, 23, 255)       # --bg
INK = (230, 237, 243, 255)   # --ink
ACCENT = (201, 48, 48, 255)  # --accent
BORDER = (33, 38, 45, 255)

def find_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def find_mono_font(size):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def make_icon(size, maskable=False, out_path="icon.png"):
    img = Image.new("RGBA", (size, size), BG)
    draw = ImageDraw.Draw(img)

    # Rounded corners — but for maskable, no corners (full bleed)
    if not maskable:
        # Cut to rounded square
        radius = int(size * 0.19)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, size, size), radius=radius, fill=255)
        img.putalpha(mask)
        # Reapply background under alpha
        bg_layer = Image.new("RGBA", (size, size), BG)
        bg_layer.paste(img, (0, 0), img)
        img = bg_layer
        draw = ImageDraw.Draw(img)

    # For maskable, content needs to fit within the safe zone (inner 80%)
    safe = 0.8 if maskable else 1.0
    cx = size / 2
    cy = size / 2

    # Inner border ring (case-file accent)
    if not maskable:
        inset = int(size * 0.094)
        rr = int(size * 0.125)
        draw.rounded_rectangle(
            (inset, inset, size - inset, size - inset),
            radius=rr, outline=BORDER, width=max(1, int(size / 256))
        )

    # Magnifying glass: circle + handle
    glass_r = size * 0.23 * safe
    glass_cx = cx - size * 0.08 * safe
    glass_cy = cy - size * 0.08 * safe
    glass_w = max(2, int(size * 0.035))

    # Circle
    draw.ellipse(
        (glass_cx - glass_r, glass_cy - glass_r,
         glass_cx + glass_r, glass_cy + glass_r),
        outline=INK, width=glass_w
    )

    # Handle (diagonal line)
    handle_start_x = glass_cx + glass_r * 0.707
    handle_start_y = glass_cy + glass_r * 0.707
    handle_end_x = handle_start_x + size * 0.18 * safe
    handle_end_y = handle_start_y + size * 0.18 * safe
    handle_w = max(3, int(size * 0.043))
    draw.line(
        [(handle_start_x, handle_start_y), (handle_end_x, handle_end_y)],
        fill=INK, width=handle_w
    )

    # Big "C" inside the glass — Case File monogram
    c_size = int(glass_r * 1.6)
    font = find_font(c_size, bold=True)
    text = "C"
    # Compute size to center
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = glass_cx - tw / 2 - bbox[0]
    ty = glass_cy - th / 2 - bbox[1] - size * 0.01
    draw.text((tx, ty), text, font=font, fill=ACCENT)

    # Confidential stamp band at the bottom (skip for small icons & maskable)
    if size >= 192 and not maskable:
        band_w = size * 0.45
        band_h = size * 0.085
        band_y = size - size * 0.13
        # Slightly rotated stamp - approximate with a rectangle (PIL rotated text is hard)
        bx0 = cx - band_w / 2
        bx1 = cx + band_w / 2
        by0 = band_y - band_h / 2
        by1 = band_y + band_h / 2
        # Build stamp on a transparent canvas and rotate it
        stamp_size = (int(band_w * 1.3), int(band_h * 2))
        stamp = Image.new("RGBA", stamp_size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(stamp)
        sx0 = (stamp_size[0] - band_w) / 2
        sy0 = (stamp_size[1] - band_h) / 2
        sd.rounded_rectangle(
            (sx0, sy0, sx0 + band_w, sy0 + band_h),
            radius=4, outline=ACCENT, width=max(2, int(size / 200))
        )
        stamp_font = find_mono_font(int(band_h * 0.55))
        stamp_text = "CONFIDENTIAL"
        sb = sd.textbbox((0, 0), stamp_text, font=stamp_font)
        stw = sb[2] - sb[0]
        sth = sb[3] - sb[1]
        sd.text(
            ((stamp_size[0] - stw) / 2 - sb[0],
             (stamp_size[1] - sth) / 2 - sb[1]),
            stamp_text, font=stamp_font, fill=ACCENT
        )
        stamp = stamp.rotate(-3, resample=Image.BICUBIC, expand=False)
        img.paste(stamp, (int(cx - stamp_size[0] / 2), int(band_y - stamp_size[1] / 2)), stamp)

    img.save(out_path, "PNG", optimize=True)
    print(f"Wrote {out_path} ({size}x{size}{', maskable' if maskable else ''})")

if __name__ == "__main__":
    out = "/home/claude/conan-tracker/icons"
    os.makedirs(out, exist_ok=True)
    make_icon(192, maskable=False, out_path=f"{out}/icon-192.png")
    make_icon(512, maskable=False, out_path=f"{out}/icon-512.png")
    make_icon(512, maskable=True, out_path=f"{out}/icon-maskable-512.png")
