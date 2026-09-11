#!/usr/bin/env python3
"""Cut per-cell top-down map images into XYZ (Web Mercator) tiles for Grafana's Geomap panel.

Input: a directory of {cx}_{cy}.webp|png|jpg images, one per 256x256-tile map cell,
all the same size (e.g. 1024x1024 = 4 px per world tile, as published by pzfans.com).
The world origin (cell 0,0 top-left) is placed at the equator at 1 metre per world
tile, the same projection as tile_map.py, so dashboards keep using

    lon = x / 111319.4908    lat = -y / 111319.4908

Usage: tile_cells.py CELLDIR OUTDIR [--cell-tiles 256] [--min-zoom 10] [--max-zoom 19] [--quality 80]
Output: OUTDIR/{z}/{x}/{y}.webp, transparent where there is no map data.
Memory stays small: cells are loaded on demand with a bounded cache.
"""
import argparse
import math
import os
import re
import sys
from collections import OrderedDict

from PIL import Image

ORIGIN = 20037508.342789244
TILE = 256


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("celldir")
    ap.add_argument("outdir")
    ap.add_argument("--cell-tiles", type=int, default=256, help="world tiles per cell side")
    ap.add_argument("--min-zoom", type=int, default=10)
    ap.add_argument("--max-zoom", type=int, default=19)
    ap.add_argument("--quality", type=int, default=80)
    a = ap.parse_args()

    cells = {}
    for f in os.listdir(a.celldir):
        m = re.match(r"(\d+)_(\d+)\.(webp|png|jpg)$", f)
        if m:
            cells[(int(m.group(1)), int(m.group(2)))] = os.path.join(a.celldir, f)
    if not cells:
        sys.exit("no cell images found")
    probe = Image.open(next(iter(cells.values())))
    cell_px = probe.size[0]
    ppt = cell_px / a.cell_tiles  # source pixels per world tile
    max_cx = max(c[0] for c in cells)
    max_cy = max(c[1] for c in cells)
    print(f"{len(cells)} cells, {cell_px}px per cell = {ppt:g} px/tile, grid {max_cx + 1}x{max_cy + 1}", flush=True)

    cache = OrderedDict()

    def get_cell(key, k):
        """Cell image reduced by integer factor k (cached)."""
        ck = (key, k)
        if ck in cache:
            cache.move_to_end(ck)
            return cache[ck]
        img = Image.open(cells[key]).convert("RGB")
        if k > 1:
            img = img.reduce(k)
        cache[ck] = img
        if len(cache) > 48:
            cache.popitem(last=False)
        return img

    total = 0
    for z in range(a.max_zoom, a.min_zoom - 1, -1):
        res = 2 * ORIGIN / (TILE * 2**z)          # metres (world tiles) per output pixel
        span = TILE * res                          # world tiles per output tile
        src_per_out = res * ppt                    # source pixels per output pixel
        k = max(1, int(src_per_out))               # integer pre-reduction of cells
        cell_world = a.cell_tiles
        tx0 = int(ORIGIN // span)
        ty0 = int(ORIGIN // span)
        tx1 = int((ORIGIN + (max_cx + 1) * cell_world) // span)
        ty1 = int((ORIGIN + (max_cy + 1) * cell_world) // span)
        n = 0
        for tx in range(tx0, tx1 + 1):
            left = tx * span - ORIGIN              # in world tiles
            for ty in range(ty0, ty1 + 1):
                top = ty * span - ORIGIN
                c0x, c1x = int(math.floor(left / cell_world)), int(math.ceil((left + span) / cell_world)) - 1
                c0y, c1y = int(math.floor(top / cell_world)), int(math.ceil((top + span) / cell_world)) - 1
                hit = [(cx, cy) for cx in range(c0x, c1x + 1) for cy in range(c0y, c1y + 1) if (cx, cy) in cells]
                if not hit:
                    continue
                tile = Image.new("RGBA", (TILE, TILE), (0, 0, 0, 0))
                for (cx, cy) in hit:
                    # overlap of this cell with the tile, in world tiles
                    ox0, oy0 = max(left, cx * cell_world), max(top, cy * cell_world)
                    ox1, oy1 = min(left + span, (cx + 1) * cell_world), min(top + span, (cy + 1) * cell_world)
                    if ox1 <= ox0 or oy1 <= oy0:
                        continue
                    img = get_cell((cx, cy), k)
                    s = ppt / k                    # reduced source px per world tile
                    box = (int(round((ox0 - cx * cell_world) * s)), int(round((oy0 - cy * cell_world) * s)),
                           int(round((ox1 - cx * cell_world) * s)), int(round((oy1 - cy * cell_world) * s)))
                    if box[2] <= box[0] or box[3] <= box[1]:
                        continue
                    part = img.crop(box)
                    # pure black in the source is "no map data": make it transparent
                    part.putalpha(part.convert("L").point(lambda v: 255 if v > 4 else 0))
                    w = max(1, int(round((ox1 - ox0) / res)))
                    h = max(1, int(round((oy1 - oy0) / res)))
                    part = part.resize((w, h), Image.LANCZOS)
                    tile.alpha_composite(part, (int(round((ox0 - left) / res)), int(round((oy0 - top) / res))))
                d = os.path.join(a.outdir, str(z), str(tx))
                os.makedirs(d, exist_ok=True)
                tile.save(os.path.join(d, f"{ty}.webp"), quality=a.quality, method=4)
                n += 1
        total += n
        print(f"z{z}: {n} tiles ({res:.3f} tiles/px, source reduce {k})", flush=True)
    print(f"done: {total} tiles", flush=True)


if __name__ == "__main__":
    main()
