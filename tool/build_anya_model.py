#!/usr/bin/env python3
"""アーニャ画像から立体的な 3D モデル (glTF Binary) を生成する。

板ポリではなく、シルエットから厚みを起こした「インフレーション」メッシュを作る:

- 元画像を取得 -> 透明部分をトリミング -> テクスチャ化
- アルファのシルエットから距離変換を取り、中心ほど厚くなる高さ場を作る
- 高さ場を前面 / 背面に押し出した閉じたメッシュ + 台座を出力
- "Spin" / "Bounce" の 2 アニメーションを埋め込む

使い方:
    python3 tool/build_anya_model.py

必要: Pillow (pip install Pillow)
"""

from __future__ import annotations

import io
import json
import math
import struct
import subprocess
import urllib.request
from pathlib import Path

from PIL import Image

SOURCE_URL = "https://spy-family.net/tvseries/assets/img/top/chara_anya_1.png"
ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "assets" / "anya"
SOURCE_PNG = ASSET_DIR / "anya_source.png"
OUTPUT_GLB = ASSET_DIR / "anya.glb"

MODEL_HEIGHT = 2.0        # 立ち姿の高さ (glTF 単位)
DEPTH_SCALE = 0.34        # 片面あたりの最大の厚み
DEPTH_FALLOFF = 0.62      # 高さ場の丸み (小さいほど平たく、1 に近いほど尖る)
GRID_WIDTH = 256          # 横方向の頂点数。縦は画像のアスペクトから決まる
SMOOTH_PASSES = 3         # 高さ場のならし回数
PEDESTAL_HEIGHT = 0.09
MAX_TEXTURE_EDGE = 1024

# 距離変換 (chamfer 3-4) の重み。1 ピクセル = 3。
_ORTHOGONAL = 3
_DIAGONAL = 4

# glTF 定数
FLOAT = 5126
UNSIGNED_INT = 5125
ARRAY_BUFFER = 34962
ELEMENT_ARRAY_BUFFER = 34963


class BufferBuilder:
    """bufferView / accessor を積み上げてバイナリチャンクを組み立てる。"""

    def __init__(self) -> None:
        self.data = bytearray()
        self.buffer_views: list[dict] = []
        self.accessors: list[dict] = []

    def _align(self) -> None:
        while len(self.data) % 4:
            self.data.append(0)

    def add_view(self, payload: bytes, target: int | None = None) -> int:
        self._align()
        view = {"buffer": 0, "byteOffset": len(self.data), "byteLength": len(payload)}
        if target is not None:
            view["target"] = target
        self.data.extend(payload)
        self.buffer_views.append(view)
        return len(self.buffer_views) - 1

    def add_accessor(
        self,
        values: list,
        component_type: int,
        type_: str,
        target: int | None = None,
        with_bounds: bool = False,
    ) -> int:
        components = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[type_]
        fmt = {FLOAT: "f", UNSIGNED_INT: "I"}[component_type]
        flat: list[float] = []
        for value in values:
            if isinstance(value, (list, tuple)):
                flat.extend(value)
            else:
                flat.append(value)
        payload = struct.pack(f"<{len(flat)}{fmt}", *flat)
        view_index = self.add_view(payload, target)
        accessor = {
            "bufferView": view_index,
            "componentType": component_type,
            "count": len(flat) // components,
            "type": type_,
        }
        if with_bounds:
            if components == 1:
                accessor["min"] = [min(flat)]
                accessor["max"] = [max(flat)]
            else:
                columns = [flat[i::components] for i in range(components)]
                accessor["min"] = [min(c) for c in columns]
                accessor["max"] = [max(c) for c in columns]
        self.accessors.append(accessor)
        return len(self.accessors) - 1


def download(url: str, destination: Path) -> None:
    """urllib -> curl の順に試す (python.org 版 Python は CA 証明書を持たないことがある)。"""
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            destination.write_bytes(response.read())
            return
    except Exception as error:  # noqa: BLE001 - curl フォールバックに委ねる
        print(f"urllib failed ({error}); falling back to curl")
    subprocess.run(
        ["curl", "-sSLf", "-A", "Mozilla/5.0", "-o", str(destination), url],
        check=True,
    )


def fetch_source_image() -> Image.Image:
    if not SOURCE_PNG.exists():
        ASSET_DIR.mkdir(parents=True, exist_ok=True)
        print(f"downloading {SOURCE_URL}")
        download(SOURCE_URL, SOURCE_PNG)
    return Image.open(SOURCE_PNG).convert("RGBA")


def build_texture(image: Image.Image) -> bytes:
    if max(image.size) > MAX_TEXTURE_EDGE:
        scale = MAX_TEXTURE_EDGE / max(image.size)
        image = image.resize(
            (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
            Image.LANCZOS,
        )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def silhouette_mask(image: Image.Image, width: int) -> tuple[list[list[bool]], int, int]:
    """アルファを格子解像度に落とし、内側かどうかの真偽値グリッドにする。"""
    height = max(2, round(width * image.height / image.width))
    alpha = image.getchannel("A").resize((width, height), Image.BILINEAR)
    pixels = alpha.load()
    mask = [[pixels[x, y] > 127 for x in range(width)] for y in range(height)]
    return mask, width, height


def distance_field(mask: list[list[bool]], width: int, height: int) -> list[list[float]]:
    """外側からの距離 (chamfer 3-4) を求める。外側は 0。"""
    infinity = float("inf")
    distance = [
        [infinity if mask[y][x] else 0.0 for x in range(width)] for y in range(height)
    ]

    # 前方走査 (左上 -> 右下)
    for y in range(height):
        row = distance[y]
        previous = distance[y - 1] if y > 0 else None
        for x in range(width):
            if row[x] == 0.0:
                continue
            best = row[x]
            if x > 0:
                best = min(best, row[x - 1] + _ORTHOGONAL)
            if previous is not None:
                best = min(best, previous[x] + _ORTHOGONAL)
                if x > 0:
                    best = min(best, previous[x - 1] + _DIAGONAL)
                if x + 1 < width:
                    best = min(best, previous[x + 1] + _DIAGONAL)
            row[x] = best

    # 後方走査 (右下 -> 左上)
    for y in range(height - 1, -1, -1):
        row = distance[y]
        nxt = distance[y + 1] if y + 1 < height else None
        for x in range(width - 1, -1, -1):
            if row[x] == 0.0:
                continue
            best = row[x]
            if x + 1 < width:
                best = min(best, row[x + 1] + _ORTHOGONAL)
            if nxt is not None:
                best = min(best, nxt[x] + _ORTHOGONAL)
                if x + 1 < width:
                    best = min(best, nxt[x + 1] + _DIAGONAL)
                if x > 0:
                    best = min(best, nxt[x - 1] + _DIAGONAL)
            row[x] = best

    # 到達しなかったセル (全面が内側の場合など) を潰す
    for row in distance:
        for x, value in enumerate(row):
            if value == infinity:
                row[x] = 0.0
    return distance


def height_field(
    mask: list[list[bool]],
    distance: list[list[float]],
    width: int,
    height: int,
) -> list[list[float]]:
    """距離場を丸みのある高さ場に変換し、数回ならす。"""
    # シルエットの最外周が 0 になるよう 1 ピクセル分内側に寄せる。
    effective = [
        [max(0.0, distance[y][x] - _ORTHOGONAL) for x in range(width)]
        for y in range(height)
    ]
    peak = max((value for row in effective for value in row), default=0.0)
    if peak <= 0:
        raise ValueError("シルエットが薄すぎて厚みを作れませんでした")

    field = [
        [
            DEPTH_SCALE * (effective[y][x] / peak) ** DEPTH_FALLOFF if mask[y][x] else 0.0
            for x in range(width)
        ]
        for y in range(height)
    ]

    for _ in range(SMOOTH_PASSES):
        smoothed = [row[:] for row in field]
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                if not mask[y][x]:
                    continue
                smoothed[y][x] = (
                    field[y][x] * 4
                    + field[y - 1][x]
                    + field[y + 1][x]
                    + field[y][x - 1]
                    + field[y][x + 1]
                ) / 8
        field = smoothed
    return field


def dilate(mask: list[list[bool]], width: int, height: int) -> list[list[bool]]:
    """シルエットを 1 セル分外へ広げる。

    メッシュの境界を格子で切ると指先などが階段状に欠けるため、少し外まで面を張り、
    細かい輪郭はテクスチャのアルファ (alphaMode: MASK) に切り抜かせる。
    """
    grown = [[False] * width for _ in range(height)]
    for y in range(height):
        for x in range(width):
            if not mask[y][x]:
                continue
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < height and 0 <= nx < width:
                        grown[ny][nx] = True
    return grown


def inflated_geometry(
    mask: list[list[bool]],
    field: list[list[float]],
    width: int,
    height: int,
    model_width: float,
) -> tuple[list, list, list, list]:
    """高さ場を前後に押し出した閉じたメッシュを作る。"""
    surface = dilate(mask, width, height)
    step_x = model_width / (width - 1)
    step_y = MODEL_HEIGHT / (height - 1)

    positions: list[tuple[float, float, float]] = []
    normals: list[tuple[float, float, float]] = []
    uvs: list[tuple[float, float]] = []
    # front[y][x] / back[y][x] -> 頂点インデックス
    front_index = [[-1] * width for _ in range(height)]
    back_index = [[-1] * width for _ in range(height)]

    def sample(x: int, y: int) -> float:
        x = min(max(x, 0), width - 1)
        y = min(max(y, 0), height - 1)
        return field[y][x]

    for y in range(height):
        for x in range(width):
            if not surface[y][x]:
                continue
            depth = field[y][x]
            px = (x / (width - 1) - 0.5) * model_width
            py = (1 - y / (height - 1)) * MODEL_HEIGHT
            u = x / (width - 1)
            v = y / (height - 1)

            # 高さ場の勾配から法線を求める (y は画像座標なので上下反転)
            dzdx = (sample(x + 1, y) - sample(x - 1, y)) / (2 * step_x)
            dzdy = (sample(x, y - 1) - sample(x, y + 1)) / (2 * step_y)
            length = math.sqrt(dzdx * dzdx + dzdy * dzdy + 1.0)

            front_index[y][x] = len(positions)
            positions.append((px, py, depth))
            normals.append((-dzdx / length, -dzdy / length, 1.0 / length))
            uvs.append((u, v))

            back_index[y][x] = len(positions)
            positions.append((px, py, -depth))
            normals.append((-dzdx / length, -dzdy / length, -1.0 / length))
            uvs.append((u, v))

    indices: list[int] = []
    for y in range(height - 1):
        for x in range(width - 1):
            corners = (
                surface[y][x],
                surface[y][x + 1],
                surface[y + 1][x],
                surface[y + 1][x + 1],
            )
            if not all(corners):
                continue
            # 完全にシルエット外の面は張らない
            if not (mask[y][x] or mask[y][x + 1] or mask[y + 1][x] or mask[y + 1][x + 1]):
                continue
            # 画像座標の上下と 3D の上下が逆なので、前面は (y+1) 側が下になる
            a = front_index[y][x]
            b = front_index[y][x + 1]
            c = front_index[y + 1][x + 1]
            d = front_index[y + 1][x]
            indices.extend([a, d, c, a, c, b])

            a = back_index[y][x]
            b = back_index[y][x + 1]
            c = back_index[y + 1][x + 1]
            d = back_index[y + 1][x]
            indices.extend([a, c, d, a, b, c])

    return positions, normals, uvs, indices


def pedestal_geometry(radius: float, height: float, segments: int = 48):
    """上面 + 側面の円柱 (底面は見えないので省略)。"""
    positions: list[tuple[float, float, float]] = []
    normals: list[tuple[float, float, float]] = []
    indices: list[int] = []

    top_center = len(positions)
    positions.append((0.0, 0.0, 0.0))
    normals.append((0.0, 1.0, 0.0))
    top_start = len(positions)
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        positions.append((radius * math.cos(angle), 0.0, radius * math.sin(angle)))
        normals.append((0.0, 1.0, 0.0))
    for i in range(segments):
        indices.extend([top_center, top_start + (i + 1) % segments, top_start + i])

    side_start = len(positions)
    for i in range(segments + 1):
        angle = 2 * math.pi * i / segments
        nx, nz = math.cos(angle), math.sin(angle)
        positions.append((radius * nx, 0.0, radius * nz))
        normals.append((nx, 0.0, nz))
        positions.append((radius * nx, -height, radius * nz))
        normals.append((nx, 0.0, nz))
    for i in range(segments):
        a = side_start + i * 2
        indices.extend([a, a + 1, a + 3, a, a + 3, a + 2])

    return positions, normals, indices


def spin_animation_data(duration: float = 8.0, steps: int = 8):
    times = [duration * i / steps for i in range(steps + 1)]
    rotations = []
    for i in range(steps + 1):
        angle = 2 * math.pi * i / steps
        rotations.append((0.0, math.sin(angle / 2), 0.0, math.cos(angle / 2)))
    return times, rotations


def bounce_animation_data(duration: float = 1.1, height: float = 0.22, samples: int = 24):
    times = [duration * i / samples for i in range(samples + 1)]
    offsets = []
    for t in times:
        phase = math.sin(math.pi * t / duration)
        offsets.append((0.0, height * (phase ** 0.7), 0.0))
    return times, offsets


def build_glb() -> None:
    image = fetch_source_image()
    bbox = image.getbbox()
    if bbox:
        image = image.crop(bbox)
    aspect = image.width / image.height
    model_width = MODEL_HEIGHT * aspect

    texture_png = build_texture(image)

    mask, grid_w, grid_h = silhouette_mask(image, GRID_WIDTH)
    distance = distance_field(mask, grid_w, grid_h)
    field = height_field(mask, distance, grid_w, grid_h)
    positions, normals, uvs, indices = inflated_geometry(
        mask, field, grid_w, grid_h, model_width
    )

    builder = BufferBuilder()
    body_position = builder.add_accessor(positions, FLOAT, "VEC3", ARRAY_BUFFER, with_bounds=True)
    body_normal = builder.add_accessor(normals, FLOAT, "VEC3", ARRAY_BUFFER)
    body_uv = builder.add_accessor(uvs, FLOAT, "VEC2", ARRAY_BUFFER)
    body_index = builder.add_accessor(indices, UNSIGNED_INT, "SCALAR", ELEMENT_ARRAY_BUFFER)

    ped_positions, ped_normals, ped_indices = pedestal_geometry(model_width * 0.3, PEDESTAL_HEIGHT)
    ped_position = builder.add_accessor(ped_positions, FLOAT, "VEC3", ARRAY_BUFFER, with_bounds=True)
    ped_normal = builder.add_accessor(ped_normals, FLOAT, "VEC3", ARRAY_BUFFER)
    ped_index = builder.add_accessor(ped_indices, UNSIGNED_INT, "SCALAR", ELEMENT_ARRAY_BUFFER)

    spin_times, spin_rotations = spin_animation_data()
    spin_input = builder.add_accessor(spin_times, FLOAT, "SCALAR", with_bounds=True)
    spin_output = builder.add_accessor(spin_rotations, FLOAT, "VEC4")

    bounce_times, bounce_offsets = bounce_animation_data()
    bounce_input = builder.add_accessor(bounce_times, FLOAT, "SCALAR", with_bounds=True)
    bounce_output = builder.add_accessor(bounce_offsets, FLOAT, "VEC3")

    image_view = builder.add_view(texture_png)

    gltf = {
        "asset": {"version": "2.0", "generator": "flutter_speckit_app/tool/build_anya_model.py"},
        "scene": 0,
        "scenes": [{"name": "AnyaScene", "nodes": [0]}],
        "nodes": [
            {"name": "AnyaRoot", "children": [1, 2], "rotation": [0.0, 0.0, 0.0, 1.0]},
            {"name": "AnyaBody", "mesh": 0, "translation": [0.0, 0.0, 0.0]},
            {"name": "Pedestal", "mesh": 1},
        ],
        "meshes": [
            {
                "name": "AnyaBody",
                "primitives": [
                    {
                        "attributes": {
                            "POSITION": body_position,
                            "NORMAL": body_normal,
                            "TEXCOORD_0": body_uv,
                        },
                        "indices": body_index,
                        "material": 0,
                    }
                ],
            },
            {
                "name": "Pedestal",
                "primitives": [
                    {
                        "attributes": {"POSITION": ped_position, "NORMAL": ped_normal},
                        "indices": ped_index,
                        "material": 1,
                    }
                ],
            },
        ],
        "materials": [
            {
                "name": "AnyaMaterial",
                "pbrMetallicRoughness": {
                    "baseColorTexture": {"index": 0},
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.85,
                },
                "alphaMode": "MASK",
                "alphaCutoff": 0.5,
                "doubleSided": False,
            },
            {
                "name": "PedestalMaterial",
                "pbrMetallicRoughness": {
                    "baseColorFactor": [0.94, 0.72, 0.83, 1.0],
                    "metallicFactor": 0.1,
                    "roughnessFactor": 0.55,
                },
                "doubleSided": False,
            },
        ],
        "textures": [{"sampler": 0, "source": 0}],
        "images": [{"bufferView": image_view, "mimeType": "image/png", "name": "anya"}],
        "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}],
        "animations": [
            {
                "name": "Spin",
                "samplers": [{"input": spin_input, "output": spin_output, "interpolation": "LINEAR"}],
                "channels": [{"sampler": 0, "target": {"node": 0, "path": "rotation"}}],
            },
            {
                "name": "Bounce",
                "samplers": [{"input": bounce_input, "output": bounce_output, "interpolation": "LINEAR"}],
                "channels": [{"sampler": 0, "target": {"node": 1, "path": "translation"}}],
            },
        ],
        "accessors": builder.accessors,
        "bufferViews": builder.buffer_views,
        "buffers": [{"byteLength": len(builder.data)}],
    }

    json_chunk = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_chunk += b" " * ((4 - len(json_chunk) % 4) % 4)
    bin_chunk = bytes(builder.data)
    bin_chunk += b"\x00" * ((4 - len(bin_chunk) % 4) % 4)

    total = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    glb = bytearray()
    glb.extend(struct.pack("<III", 0x46546C67, 2, total))
    glb.extend(struct.pack("<II", len(json_chunk), 0x4E4F534A))
    glb.extend(json_chunk)
    glb.extend(struct.pack("<II", len(bin_chunk), 0x004E4942))
    glb.extend(bin_chunk)

    OUTPUT_GLB.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_GLB.write_bytes(glb)

    peak_depth = max(max(row) for row in field)
    print(f"wrote {OUTPUT_GLB.relative_to(ROOT)} ({len(glb) / 1024 / 1024:.2f} MB)")
    print(f"  grid: {grid_w} x {grid_h}")
    print(f"  vertices: {len(positions)}, triangles: {len(indices) // 3}")
    print(f"  size: {model_width:.2f} x {MODEL_HEIGHT:.2f} x {peak_depth * 2:.2f}")
    print("  animations: Spin, Bounce")


if __name__ == "__main__":
    build_glb()
