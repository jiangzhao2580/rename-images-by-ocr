# 图片按 OCR 批量重命名工具（rename-images-by-ocr）

> 自动识别照片中**叠加（后期合成）**的「姓名 / 地址 + 门牌号」，将文件名批量改为
> `姓名地址_门牌号.原扩展名`。支持 EasyOCR / RapidOCR / Tesseract 三种 OCR 后端，可拖拽运行。

- **Author:** CPPU-Jiang
- **仓库：** `rename-images-by-ocr`

---

## 一、项目简介

`rename_images_by_ocr.py` 是一个用于**基层入户走访 / 信息采集**场景的小工具：

很多手机照片在拍照后，会用图片编辑工具在画面上**手写或叠加**了住户的姓名、地址和门牌号
（例如画面底部写着「田建英，富康巷28」）。本脚本用 OCR 把这些文字读出来，
自动把文件名改成 `姓名地址_门牌号`（如 `田建英富康巷_28.jpg`），方便后续按人名/门牌检索归档。

- 纯 Python，跨平台（Windows / macOS / Linux）。
- 读图统一用 `PIL + numpy`，**不再直接把中文路径传给 OpenCV**，可避开中文路径与特殊格式问题。
- 只保留图片**下半部分**的文字结果，自动过滤上方门楣 / 招牌等干扰。

---

## 二、功能特性

- **三种 OCR 后端**，任选其一：
  - `rapidocr`（默认推荐）：`pip install rapidocr-onnxruntime`，模型随 pip 一起下载，**无需额外联网**。
  - `easyocr`：中文识别好，但**首次运行要联网下载模型**。
  - `tesseract`：需额外安装 Tesseract-OCR 引擎与中文语言包 `chi_sim.traineddata`。
- **拖拽即用**：把图片文件夹拖到 `运行图片重命名.bat` 上即可批量改名；
  拖到 `预览图片重命名.bat` 上可**只预览不改名**。
- **命令行 / 双击**两种用法，也支持把默认文件夹写死在脚本顶部 `DEFAULT_FOLDER`。
- **智能解析**：自动剔除「门牌号 / 姓名 / 住户 / 房号」等噪声标签，提取「汉字姓名+地址」与「最长数字门牌号」。
- **常见错字纠错**：通过 `CHAR_FIX` 表纠正 OCR 易错字（如 `枉 → 杜`）。
- **预览保护**：`--dry-run` 只打印「原名 → 新名」，不实际改动文件。
- **重名防冲突**：新名字若已存在，自动追加 `_1` `_2` … 后缀；批内也不会自碰撞。
- **容错**：单张识别失败不影响整批，会跳过并列出跳过清单。
- **下半区优先**：`BOTTOM_KEEP_RATIO` 控制只取图片高度以下区域的文字，去除顶部招牌干扰；
  若叠加文字不在底部，把它改成 `0.0` 即可保留全图文字。

---

## 三、依赖安装

任选一个后端安装（推荐 RapidOCR）：

```bash
pip install rapidocr-onnxruntime
# 或
pip install easyocr            # 中文识别好，但首次运行要联网下载模型
# 或
pip install pytesseract pillow # 并额外安装 Tesseract-OCR 引擎，且把 chi_sim.traineddata 放入 tessdata
```

> 注：所有后端都用 `PIL + numpy` 读图，无需 OpenCV。

---

## 四、使用方法（三选一，最推荐第一种）

1. **拖拽（最简单）**
   - 把【图片文件夹】拖到 `运行图片重命名.bat` → 直接批量重命名。
   - 把【图片文件夹】拖到 `预览图片重命名.bat` → 只预览、不改名。
2. **命令行**
   ```bash
   python rename_images_by_ocr.py "D:/图片/待处理"
   python rename_images_by_ocr.py "D:/图片/待处理" --dry-run   # 预览
   ```
3. **改默认文件夹后双击**
   把脚本顶部 `DEFAULT_FOLDER` 改成你的文件夹，然后双击 `运行图片重命名.bat`。

---

## 五、命令行参数

| 参数 | 说明 |
| --- | --- |
| `folder` | 目标文件夹路径（可直接把文件夹拖到脚本/启动器上）；缺省用 `DEFAULT_FOLDER`。 |
| `--separator` | 姓名与门牌号之间的分隔符，默认 `_`。 |
| `--backend` | OCR 后端：`easyocr` / `rapidocr` / `tesseract`，默认 `easyocr`。 |
| `--recursive` | 递归遍历子文件夹。 |
| `--dry-run` | 只预览，不实际重命名。 |

---

## 六、脚本顶部配置区（可直接修改，或被命令行覆盖）

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `DEFAULT_FOLDER` | `C:\Users\13444\Desktop\溢渡村2_compressed` | 默认目标文件夹。 |
| `SEPARATOR` | `_` | 姓名与门牌号之间的分隔符。 |
| `IMAGE_EXTS` | `.jpg .jpeg .png .bmp .webp .tif .tiff` | 支持的图片扩展名。 |
| `DEFAULT_BACKEND` | `easyocr` | 默认 OCR 后端。 |
| `MIN_CONF` | `0.35` | 只保留置信度 ≥ 该值的 OCR 结果，过滤阴影/噪点。 |
| `CHAR_FIX` | `{"枉": "杜"}` | 姓名常见错字纠错表：`{识别字: 正确字}`。 |
| `BOTTOM_KEEP_RATIO` | `0.35` | 只保留图片高度 35% 以下（下半部分）的文字；改为 `0.0` 保留全图。 |

---

## 七、识别原理（简要）

1. `load_for_ocr`：用 `PIL` 读图并转 RGB，短边不足 1200px 时放大；正常不做对比度变换（避免把地面纹理放大成噪点），仅在识别失败重试时叠加「自动对比度 + 锐化」帮助红字从杂乱背景中凸显。
2. `_filter_text`：对 OCR 结果做「置信度 + 垂直位置」过滤——只保留图片下半区的文字，去掉上方门楣/招牌。
3. `parse_name_number`：剔除噪声标签后，把汉字按原顺序拼接成「姓名+地址」，取最长连续数字段作为门牌号；再应用 `CHAR_FIX` 纠错。
4. `resolve_target`：计算不冲突的目标路径（重名自动加 `_1`/`_2`…）。

---

## 八、注意事项

- 若图片实际是 **HEIC / HEIF** 但扩展名是 `.jpg`，请先 `pip install pillow-heif` 或先用工具批量转码。
- OCR 不是 100% 准确，建议第一次先用 `预览图片重命名.bat`（`--dry-run`）核对结果，确认无误再正式改名。
- 改名是不可逆操作，**正式运行前请备份原图**。

---

## 九、文件清单

| 文件 | 作用 |
| --- | --- |
| `rename_images_by_ocr.py` | 主程序（核心逻辑）。 |
| `运行图片重命名.bat` | Windows 启动器：拖入文件夹即批量重命名。 |
| `预览图片重命名.bat` | Windows 启动器：拖入文件夹仅预览（`--dry-run`）。 |

> 两个 `.bat` 均通过 `python "%~dp0rename_images_by_ocr.py" %*` 调用同目录脚本，
> 因此需与主程序放在同一文件夹内使用。

---

## 十、系统要求

- Python 3.8+，并安装所选 OCR 后端依赖（见第三节）。
- Windows 用户可直接用附带的 `.bat` 启动器；macOS / Linux 用户用命令行运行。

---

## 十一、作者与许可

- **Author:** CPPU-Jiang
- 本工具以「现状」提供，仅供学习与个人使用。如需添加开源许可证，可在本仓库另行声明。
