#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rename_images_by_ocr.py
========================
批量重命名图片：自动识别图中叠加（后期合成）的「姓名/地址 + 门牌号」，
把文件重命名为 「姓名地址{分隔符}门牌号.原扩展名」。

典型场景：手机相册里每张照片都用编辑工具手写/叠加了住户姓名、地址和门牌号，
例如 "田建英，富康巷28"，本脚本把文字读出来并改成文件名。

依赖（任选其一，推荐 RapidOCR，模型随 pip 一起下载，无需额外联网）：
    pip install rapidocr-onnxruntime
    # 或
    pip install easyocr          # 中文识别好，但首次运行要联网下载模型
    # 或
    pip install pytesseract pillow
    # 并额外安装 Tesseract-OCR 引擎，且把中文语言包 chi_sim.traineddata 放入 tessdata

注意：所有后端都使用 PIL + numpy 读图，不再直接传文件路径给 OpenCV，可避开中文路径和特殊格式问题。
识别时只保留图片下半部分的文字结果，可去掉上方门楣/招牌；若叠加文字不在底部，
把 BOTTOM_KEEP_RATIO 改成 0.0 即可保留整张图的所有文字。
若图片实际是 HEIC/HEIF 格式但扩展名为 .jpg，请先安装 pip install pillow-heif 或先用工具批量转码。

用法（三选一，最推荐第一种）：
    1) 把【图片文件夹】直接拖到本脚本 / 启动器(.bat) 上即可运行
    2) 命令行：python rename_images_by_ocr.py "D:/图片/待处理"
    3) 改脚本顶部 DEFAULT_FOLDER 为你的文件夹，然后双击运行
    预览（不改名）：python rename_images_by_ocr.py "D:/图片/待处理" --dry-run
"""

import argparse
import re
import sys
from pathlib import Path

# ===================== 配置区（可直接修改，也可走命令行参数覆盖） =====================
DEFAULT_FOLDER  = r"C:\Users\13444\Desktop\溢渡村2_compressed"      # 默认目标文件夹；也可把文件夹拖到脚本上，或命令行传路径
SEPARATOR       = "_"                    # 姓名与门牌号之间的分隔符
IMAGE_EXTS      = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
DEFAULT_BACKEND = "easyocr"              # OCR 后端：easyocr / rapidocr / tesseract
MIN_CONF        = 0.35                   # 只保留置信度 >= 该值的 OCR 结果；过滤阴影/噪点，同时不误删真字
CHAR_FIX        = {"枉": "杜"}          # 姓名里常认错字的纠错表：{识别出来的字: 正确字}
BOTTOM_KEEP_RATIO = 0.35                 # 只保留图片高度 35% 以下（下半部分）的文字，去掉上方门楣/招牌
# ===================================================================================

# 汉字片段（姓名）
CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]+")
# 数字片段（门牌号）。如需保留 "5-2" 中的连字符，可改成 r"[\d\-]+"
# 若门牌号含字母（如 B1203），可改成 r"[A-Za-z0-9\-]+"
DIGIT_RE = re.compile(r"\d+")
# 常见「标签/噪声」汉字，识别到但应排除在姓名之外（可按实际图面增删）
NAME_NOISE = {"门牌号", "姓名", "住户", "房号", "编号", "室", "栋",
              "号楼", "单元", "楼", "房", "号", "之", "层"}


def load_for_ocr(path: Path, enhance: bool = False):
    """读图并预处理：只放大到 1200px。enhance=True 时再叠加对比度+锐化。

    正常情况不做对比度变换，以免把地面纹理放大成噪点；只有识别失败重试时才增强，
    帮助红字从植物等杂乱背景里凸显出来。不裁剪像素，避免切掉文字。
    """
    import numpy as np
    from PIL import Image, ImageFilter, ImageOps
    img = Image.open(path).convert("RGB")
    if max(img.size) < 1200:
        scale = 1200.0 / max(img.size)
        img = img.resize((int(img.size[0] * scale), int(img.size[1] * scale)), Image.LANCZOS)
    if enhance:
        img = ImageOps.autocontrast(img, cutoff=2)
        img = img.filter(ImageFilter.SHARPEN)
        img = img.filter(ImageFilter.SHARPEN)
    return np.array(img)


def _filter_text(results, h):
    """对 OCR 结果做 置信度 + 位置 过滤，返回拼接好的文字。results 元素为 (框, 文本, 分数)。"""
    kept = []
    for item in results:
        if len(item) < 3:
            continue
        box, text, conf = item[0], item[1], item[2]
        if conf < MIN_CONF:
            continue
        if h and BOTTOM_KEEP_RATIO < 1.0:
            ys = [p[1] for p in box]
            cy = (min(ys) + max(ys)) / 2.0
            if cy < h * BOTTOM_KEEP_RATIO:      # 跳过图片上半部分（门楣/招牌）
                continue
        kept.append(text)
    if not kept and results:                     # 过滤后没文字，回退到不过滤
        kept = [item[1] for item in results if len(item) >= 2]
    return "\n".join(line.strip() for line in kept if line.strip())


def get_ocr_engine(backend: str):
    """返回一个 ocr(path: Path) -> str 的函数，把图片中的文字识别成一个字符串。"""
    if backend == "rapidocr":
        from rapidocr_onnxruntime import RapidOCR
        engine = RapidOCR()

        def ocr(path: Path) -> str:
            arr = load_for_ocr(path)
            result, _ = engine(arr)
            text = _filter_text(result, arr.shape[0]) if result else ""
            if text and re.search(r"\d", text):     # 拿到姓名+数字就直接返回
                return text
            # 第一遍没识别全，增强（对比度+锐化）后重试一次
            arr2 = load_for_ocr(path, enhance=True)
            result2, _ = engine(arr2)
            return _filter_text(result2, arr2.shape[0]) or text or ""

        return ocr

    if backend == "easyocr":
        import easyocr
        print("[初始化] 加载 EasyOCR 中文模型（首次运行会联网下载）...", file=sys.stderr)
        reader = easyocr.Reader(["ch_sim", "en"], gpu=False)

        def ocr(path: Path) -> str:
            arr = load_for_ocr(path)
            text = _filter_text(reader.readtext(arr, detail=1), arr.shape[0])
            if text and re.search(r"\d", text):     # 拿到姓名+数字就直接返回
                return text
            # 第一遍没识别全，增强（对比度+锐化）后重试一次
            arr2 = load_for_ocr(path, enhance=True)
            return _filter_text(reader.readtext(arr2, detail=1), arr2.shape[0]) or text or ""

        return ocr

    if backend == "tesseract":
        import pytesseract
        from PIL import Image

        def ocr(path: Path) -> str:
            return pytesseract.image_to_string(Image.open(path), lang="chi_sim+eng")

        return ocr

    raise ValueError(f"不支持的 OCR 后端：{backend!r}（请用 easyocr / rapidocr / tesseract）")


def _strip_noise(s: str) -> str:
    """反复去掉首尾的常见标签词，如 '姓名王芳' -> '王芳'、'3号楼' -> '3'。"""
    changed = True
    while changed:
        changed = False
        for kw in NAME_NOISE:
            if s.startswith(kw) and len(s) > len(kw):
                s = s[len(kw):]; changed = True
            if s.endswith(kw) and len(s) > len(kw):
                s = s[:-len(kw)]; changed = True
    return s


def parse_name_number(text: str):
    """从 OCR 文本中提取 (姓名/地址, 门牌号)。识别不到则返回 ('', '')。

    策略：剔除噪声标签后，把同一行/区域内的所有汉字按原顺序拼接成「姓名+地址」部分，
    再取最长的一段连续数字作为门牌号。例如 "田建英，富康巷28" -> ("田建英富康巷", "28")。
    """
    # 先去掉整句里的噪声标签词（由长到短，避免误替换）
    for kw in sorted(NAME_NOISE, key=len, reverse=True):
        text = text.replace(kw, "")

    cjk_parts = CJK_RE.findall(text)
    digit_parts = DIGIT_RE.findall(text)

    clean = [_strip_noise(p) for p in cjk_parts if p not in NAME_NOISE]
    clean = [p for p in clean if p]                # 去掉清空后的片段
    name = "".join(clean)                          # 所有汉字按顺序拼接
    number = max(digit_parts, key=len) if digit_parts else ""  # 门牌号取最长数字片段

    # 应用纠错表（如 枉 -> 杜）
    if CHAR_FIX:
        name = "".join(CHAR_FIX.get(ch, ch) for ch in name)

    return name, number


def resolve_target(folder: Path, stem: str, ext: str, used: set):
    """计算不冲突的目标路径。used 记录本次运行已占用的名字，避免批内自碰撞。"""
    target = folder / f"{stem}{ext}"
    if (not target.exists()) and (target not in used):
        used.add(target)
        return target
    i = 1
    while True:
        candidate = folder / f"{stem}_{i}{ext}"
        if (not candidate.exists()) and (candidate not in used):
            used.add(candidate)
            return candidate
        i += 1


def iter_images(folder: Path, recursive: bool):
    """遍历文件夹（可选递归）下的全部图片文件。"""
    pattern = "**/*" if recursive else "*"
    for p in folder.glob(pattern):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
            yield p


def main():
    ap = argparse.ArgumentParser(description="按图中姓名+门牌号批量重命名图片")
    # 位置参数 folder：支持“把文件夹拖到脚本上”直接传入；缺省则用 DEFAULT_FOLDER
    ap.add_argument("folder", nargs="?", default=DEFAULT_FOLDER,
                    help="目标文件夹路径（可直接把文件夹拖到本脚本/启动器上）")
    ap.add_argument("--separator", default=SEPARATOR, help="姓名与门牌号的分隔符")
    ap.add_argument("--backend", default=DEFAULT_BACKEND,
                    choices=["easyocr", "rapidocr", "tesseract"], help="OCR 后端")
    ap.add_argument("--recursive", action="store_true", help="递归遍历子文件夹")
    ap.add_argument("--dry-run", action="store_true", help="只预览，不实际重命名")
    args = ap.parse_args()

    folder = Path(args.folder).expanduser().resolve()
    if not folder.is_dir():
        print(f"[错误] 文件夹不存在：{folder}", file=sys.stderr)
        sys.exit(1)

    ocr = get_ocr_engine(args.backend)
    used: set = set()
    renamed, skipped = [], []

    for img in iter_images(folder, args.recursive):
        try:
            text = ocr(img)
        except Exception as e:  # 单张识别失败不应中断整批
            print(f"[跳过] 识别失败 {img.name}: {e}", file=sys.stderr)
            skipped.append(img.name)
            continue

        name, number = parse_name_number(text)

        if not name or not number:
            print(f"[跳过] 未识别到完整姓名/门牌号 {img.name} -> 文本: {text!r}")
            skipped.append(img.name)
            continue

        new_stem = f"{name}{args.separator}{number}"

        # 计算出的新名字和当前名字一样 = 已经正确，直接跳过
        if new_stem == img.stem:
            print(f"[已是正确名] {img.name}")
            renamed.append((img.name, img.name))
            continue

        target = resolve_target(folder, new_stem, img.suffix.lower(), used)

        if args.dry_run:
            print(f"[预览] {img.name} -> {target.name}")
        else:
            img.rename(target)
            print(f"[重命名] {img.name} -> {target.name}")
        renamed.append((img.name, target.name))

    print(f"\n完成：成功 {len(renamed)} 张，跳过 {len(skipped)} 张。")
    if skipped:
        print("跳过列表：", ", ".join(skipped))


if __name__ == "__main__":
    main()
