#!/usr/bin/env python3
"""Cut a top-down Project Zomboid map image into XYZ (Web Mercator) tiles for Grafana's Geomap panel.

The image must be 1 pixel per world tile with the world origin at the top-left
(e.g. the b42map.com top-down export: 19968x16128 for B42). Pixels are placed
on the equator at 1 metre per world tile, so a player at world (x, y) is at

    lon = x / 111319.4908    lat = -y / 111319.4908

Usage: tile_map.py MAP.jpg OUTDIR [--min-zoom 10] [--max-zoom 18] [--quality 85]
Output: OUTDIR/{z}/{x}/{y}.webp  (~18k files for the full B42 map, zoom 10-18); area outside the map is transparent
"""
import argparse
import math
import os
import sys

from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ORIGIN = 20037508.342789244  # half the Web Mercator world, in metres
TILE = 256


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("outdir")
    ap.add_argument("--min-zoom", type=int, default=10)
    ap.add_argument("--max-zoom", type=int, default=18)
    ap.add_argument("--quality", type=int, default=85)
    a = ap.parse_args()

    img = Image.open(a.image)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.load()
    w, h = img.size
    print(f"{a.image}: {w}x{h}", flush=True)

    total = 0
    base, k = img, 1
    for z in range(a.max_zoom, a.min_zoom - 1, -1):
        res = 2 * ORIGIN / (TILE * 2**z)  # metres (= world tiles) per pixel
        span = TILE * res                 # metres per tile
        # work from an integer-downscaled copy so low zooms never touch the full image
        want = max(1, int(res))
        if want != k:
            k = want
            base = img.reduce(k)
        # image pixel (px, py) sits at mercator (px, -py); tile indices from the top-left corner
        tx0 = int((0 + ORIGIN) // span)
        tx1 = int((w + ORIGIN) // span)
        ty0 = int((ORIGIN - 0) // span)
        ty1 = int((ORIGIN + h) // span)
        n = 0
        for tx in range(tx0, tx1 + 1):
            os.makedirs(os.path.join(a.outdir, str(z), str(tx)), exist_ok=True)
            for ty in range(ty0, ty1 + 1):
                # tile bounds in image pixels (float)
                left = tx * span - ORIGIN
                top = ty * span - ORIGIN
                box = (left, top, left + span, top + span)
                if box[2] <= 0 or box[0] >= w or box[3] <= 0 or box[1] >= h:
                    continue
                # crop only the part inside the image and paste it scaled into a black tile
                il, it = max(box[0], 0), max(box[1], 0)
                ir, ib = min(box[2], w), min(box[3], h)
                part = base.crop((int(il / k), int(it / k), int(math.ceil(ir / k)), int(math.ceil(ib / k))))
                # pure black in the source is "no map data": make it transparent
                part.putalpha(part.convert("L").point(lambda v: 255 if v > 4 else 0))
                pw, ph = max(1, round((ir - il) / res)), max(1, round((ib - it) / res))
                tile = Image.new("RGBA", (TILE, TILE), (0, 0, 0, 0))
                tile.paste(part.resize((pw, ph), Image.LANCZOS), (round((il - left) / res), round((it - top) / res)))
                tile.save(os.path.join(a.outdir, str(z), str(tx), f"{ty}.webp"), quality=a.quality, method=4)
                n += 1
        total += n
        print(f"z{z}: {n} tiles (x {tx0}-{tx1}, y {ty0}-{ty1}, {res:.3f} m/px)", flush=True)
    print(f"done: {total} tiles", flush=True)


if __name__ == "__main__":
    sys.exit(main())
