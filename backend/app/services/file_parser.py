"""
文件解析服务 - 支持12种格式16种扩展名
PDF/Word/Excel/PPT/CSV/TXT/RTF/HTML/Markdown/XMind + OCR扫描件
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 支持的文件格式
SUPPORTED_FORMATS = {
    '.pdf': 'application/pdf',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.doc': 'application/msword',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.xls': 'application/vnd.ms-excel',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    '.ppt': 'application/vnd.ms-powerpoint',
    '.csv': 'text/csv',
    '.txt': 'text/plain',
    '.rtf': 'application/rtf',
    '.html': 'text/html',
    '.htm': 'text/html',
    '.md': 'text/markdown',
    '.markdown': 'text/markdown',
    '.xmind': 'application/xmind',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.bmp': 'image/bmp',
    '.tiff': 'image/tiff',
    '.tif': 'image/tiff',
    '.gif': 'image/gif',
}


def get_supported_extensions() -> list:
    return list(SUPPORTED_FORMATS.keys())


def is_supported_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in SUPPORTED_FORMATS


async def extract_text_from_file(file_path: str, max_length: int = 15000) -> Optional[str]:
    """
    从文件中提取文本内容
    支持: PDF/Word/Excel/PPT/CSV/TXT/RTF/HTML/Markdown/XMind/图片OCR
    """
    if not os.path.exists(file_path):
        logger.error(f"文件不存在: {file_path}")
        return None

    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == '.txt':
            return _read_text_file(file_path, max_length)
        elif ext == '.rtf':
            return _extract_rtf(file_path, max_length)
        elif ext in ('.html', '.htm'):
            return _extract_html(file_path, max_length)
        elif ext in ('.md', '.markdown'):
            return _read_text_file(file_path, max_length)
        elif ext == '.csv':
            return _extract_csv(file_path, max_length)
        elif ext == '.pdf':
            return _extract_pdf(file_path, max_length)
        elif ext in ('.doc', '.docx'):
            return _extract_word(file_path, max_length)
        elif ext in ('.xlsx', '.xls'):
            return _extract_excel(file_path, max_length)
        elif ext in ('.pptx', '.ppt'):
            return _extract_ppt(file_path, max_length)
        elif ext == '.xmind':
            return _extract_xmind(file_path, max_length)
        elif ext in ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.gif'):
            return _extract_image_ocr(file_path, max_length)
        else:
            logger.warning(f"不支持的文件格式: {ext}")
            return None
    except Exception as e:
        logger.error(f"文件解析失败 [{ext}]: {e}", exc_info=True)
        return None


def _read_text_file(file_path: str, max_length: int) -> str:
    """读取纯文本文件，自动探测编码"""
    encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                text = f.read(max_length)
            return text
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"无法解码文件: {file_path}")


def _extract_rtf(file_path: str, max_length: int) -> str:
    """提取RTF文件内容"""
    try:
        from striprtf.striprtf import rtf_to_text
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            rtf_content = f.read()
        text = rtf_to_text(rtf_content)
        return text[:max_length]
    except ImportError:
        logger.warning("striprtf未安装，尝试纯文本读取")
        return _read_text_file(file_path, max_length)


def _extract_html(file_path: str, max_length: int) -> str:
    """提取HTML文件内容"""
    try:
        from bs4 import BeautifulSoup
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            html = f.read()
        soup = BeautifulSoup(html, 'html.parser')
        # 移除script和style
        for tag in soup(['script', 'style']):
            tag.decompose()
        text = soup.get_text(separator='\n', strip=True)
        return text[:max_length]
    except ImportError:
        # 回退：简单正则去标签
        import re
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            html = f.read()
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:max_length]


def _extract_csv(file_path: str, max_length: int) -> str:
    """提取CSV内容为可读文本"""
    import csv
    encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                reader = csv.reader(f)
                lines = []
                for i, row in enumerate(reader):
                    if i >= 200:  # 限制行数
                        break
                    lines.append(' | '.join(row))
                text = '\n'.join(lines)
                return text[:max_length]
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"无法解码CSV文件: {file_path}")


def _extract_pdf(file_path: str, max_length: int) -> str:
    """提取PDF内容"""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text()
            if len(text) > max_length:
                break
        doc.close()
        return text[:max_length]
    except ImportError:
        logger.warning("PyMuPDF未安装，无法解析PDF")
        return None


def _extract_word(file_path: str, max_length: int) -> str:
    """提取Word文档内容"""
    try:
        import docx
        doc = docx.Document(file_path)
        text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        return text[:max_length]
    except ImportError:
        logger.warning("python-docx未安装，无法解析Word文档")
        return None


def _extract_excel(file_path: str, max_length: int) -> str:
    """提取Excel内容为可读文本"""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, data_only=True)
        lines = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            lines.append(f"=== 工作表: {sheet_name} ===")
            for row in ws.iter_rows(max_row=200, values_only=True):
                row_text = ' | '.join([str(c) if c is not None else '' for c in row])
                if row_text.strip(' |'):
                    lines.append(row_text)
                if len('\n'.join(lines)) > max_length:
                    break
        wb.close()
        return '\n'.join(lines)[:max_length]
    except ImportError:
        logger.warning("openpyxl未安装，尝试xlrd")
        try:
            import xlrd
            wb = xlrd.open_workbook(file_path)
            lines = []
            for sheet in wb.sheets():
                lines.append(f"=== 工作表: {sheet.name} ===")
                for row_idx in range(min(sheet.nrows, 200)):
                    row = [str(sheet.cell_value(row_idx, col_idx)) for col_idx in range(sheet.ncols)]
                    lines.append(' | '.join(row))
            return '\n'.join(lines)[:max_length]
        except ImportError:
            logger.warning("openpyxl和xlrd均未安装，无法解析Excel")
            return None


def _extract_ppt(file_path: str, max_length: int) -> str:
    """提取PPT内容"""
    try:
        from pptx import Presentation
        prs = Presentation(file_path)
        lines = []
        for i, slide in enumerate(prs.slides):
            lines.append(f"--- 幻灯片 {i + 1} ---")
            for shape in slide.shapes:
                if hasattr(shape, 'text') and shape.text.strip():
                    lines.append(shape.text)
        return '\n'.join(lines)[:max_length]
    except ImportError:
        logger.warning("python-pptx未安装，无法解析PPT")
        return None


def _extract_xmind(file_path: str, max_length: int) -> str:
    """提取XMind思维导图内容"""
    try:
        import zipfile
        import json
        with zipfile.ZipFile(file_path, 'r') as z:
            # XMind 8+ 使用JSON格式
            for name in z.namelist():
                if name.endswith('content.json'):
                    data = json.loads(z.read(name))
                    lines = _parse_xmind_json(data)
                    return '\n'.join(lines)[:max_length]
            # XMind旧格式
            for name in z.namelist():
                if 'content.xml' in name:
                    import xml.etree.ElementTree as ET
                    xml_data = z.read(name)
                    root = ET.fromstring(xml_data)
                    lines = []
                    _parse_xmind_xml(root, lines, 0)
                    return '\n'.join(lines)[:max_length]
        return None
    except Exception as e:
        logger.warning(f"XMind解析失败: {e}")
        return None


def _parse_xmind_json(data, depth=0) -> list:
    """解析XMind JSON结构"""
    lines = []
    if isinstance(data, list):
        for item in data:
            lines.extend(_parse_xmind_json(item, depth))
    elif isinstance(data, dict):
        title = data.get('title', '')
        if title:
            prefix = '  ' * depth
            lines.append(f"{prefix}- {title}")
        children = data.get('children', {}).get('attached', [])
        for child in children:
            lines.extend(_parse_xmind_json(child, depth + 1))
    return lines


def _parse_xmind_xml(element, lines, depth):
    """解析XMind XML结构"""
    tag = element.tag.split('}')[-1] if '}' in element.tag else element.tag
    if tag == 'topic':
        title_el = element.find('{http://www.xmind.net/xmind}title')
        if title_el is None:
            title_el = element.find('title')
        if title_el is not None and title_el.text:
            prefix = '  ' * depth
            lines.append(f"{prefix}- {title_el.text}")
    for child in element:
        _parse_xmind_xml(child, lines, depth + 1)


def _extract_image_ocr(file_path: str, max_length: int) -> str:
    """OCR图片文字识别（中英文）"""
    try:
        import pytesseract
        from PIL import Image
        
        img = Image.open(file_path)
        # 中文简体+英文
        text = pytesseract.image_to_string(img, lang='chi_sim+eng')
        return text[:max_length]
    except ImportError:
        logger.warning("pytesseract/Pillow未安装，无法进行OCR识别")
        return None
    except Exception as e:
        logger.error(f"OCR识别失败: {e}")
        return None
