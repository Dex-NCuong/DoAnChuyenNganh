import os
import re
from typing import Optional, List, Dict
from langchain.text_splitter import RecursiveCharacterTextSplitter


def parse_pdf(file_path: str) -> List[Dict]:
    """Đọc PDF và trả về list chunks với page number metadata."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        chunks = []
        for page_num, page in enumerate(doc, start=1):  # start=1 vì page bắt đầu từ 1
            text = page.get_text()
            if text.strip():
                chunks.append({
                    "content": text,
                    "metadata": {
                        "page_number": page_num,
                        "file_type": "pdf"
                    }
                })
        doc.close()
        return chunks
    except Exception as e:
        raise ValueError(f"Error parsing PDF: {str(e)}")


def parse_docx(file_path: str) -> List[Dict]:
    """Đọc DOCX và detect headings/sections."""
    try:
        from docx import Document
        doc = Document(file_path)
        chunks = []
        current_section = None
        
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
                
            # Detect heading styles (Heading 1, Heading 2, etc.)
            if para.style.name.startswith('Heading'):
                level = para.style.name.replace('Heading ', '')
                current_section = text
                chunks.append({
                    "content": text,
                    "metadata": {
                        "section": current_section,
                        "heading_level": level,
                        "file_type": "docx"
                    }
                })
            else:
                # Regular paragraph - giữ section hiện tại
                chunks.append({
                    "content": text,
                    "metadata": {
                        "section": current_section,
                        "file_type": "docx"
                    }
                })
        return chunks
    except Exception as e:
        raise ValueError(f"Error parsing DOCX: {str(e)}")


def parse_markdown(file_path: str) -> List[Dict]:
    """Đọc Markdown và detect headings (#, ##, ###)."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        chunks = []
        current_section = None
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
                
            # Detect markdown headings (# Header, ## Subheader)
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            if heading_match:
                level = len(heading_match.group(1))  # Số lượng #
                current_section = heading_match.group(2).strip()
                chunks.append({
                    "content": line,
                    "metadata": {
                        "section": current_section,
                        "heading_level": level,
                        "file_type": "md"
                    }
                })
            else:
                chunks.append({
                    "content": line,
                    "metadata": {
                        "section": current_section,
                        "file_type": "md"
                    }
                })
        return chunks
    except Exception as e:
        raise ValueError(f"Error parsing Markdown: {str(e)}")


def parse_txt(file_path: str) -> List[Dict]:
    """Đọc TXT và detect section patterns."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        chunks = []
        current_section = None
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
                
            # Detect patterns like "PHẦN 1:", "Chương 2:", "1.1", etc.
            section_patterns = [
                r'^(PHẦN|Chương|Phần|CHƯƠNG)\s+\d+[:\s]',  # PHẦN 1:, Chương 2:
                r'^\d+\.\d+[:\s]',  # 1.1, 2.3
                r'^[A-Z][A-Z\s]{5,}:',  # ALL CAPS HEADING:
            ]
            
            is_section = False
            for pattern in section_patterns:
                if re.match(pattern, stripped, re.IGNORECASE):
                    current_section = stripped.rstrip(':').strip()
                    is_section = True
                    break
            
            chunks.append({
                "content": line,
                "metadata": {
                    "section": current_section if (is_section or current_section) else None,
                    "file_type": "txt"
                }
            })
        return chunks
    except Exception as e:
        raise ValueError(f"Error parsing TXT: {str(e)}")


def parse_file(file_path: str, file_type: str) -> List[Dict]:
    """Parse file dựa trên loại file và trả về list chunks với metadata."""
    file_type_lower = file_type.lower()
    if file_type_lower == "pdf":
        return parse_pdf(file_path)
    elif file_type_lower in ["docx", "doc"]:
        return parse_docx(file_path)
    elif file_type_lower in ["md", "markdown"]:
        return parse_markdown(file_path)
    elif file_type_lower == "txt":
        return parse_txt(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")


def split_text(
    text_chunks: List[Dict],
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    separators: Optional[list[str]] = None,
) -> list[dict]:
    """Chia nhỏ chunks thành smaller chunks, giữ metadata (page_number, section).
    
    Args:
        text_chunks: List of dicts với format {"content": "...", "metadata": {...}}
    
    Returns:
        list[dict]: Mỗi dict có format {"content": "...", "metadata": {...}}
    """
    if not text_chunks:
        return []
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators or ["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )
    
    result = []
    chunk_index = 0
    
    for original_chunk in text_chunks:
        content = original_chunk.get("content", "")
        if not content or not content.strip():
            continue
            
        metadata = original_chunk.get("metadata", {})
        
        # Split nếu chunk quá lớn (chỉ khi > chunk_size * 1.5 để tránh chia quá nhỏ)
        # Nếu chunk nhỏ hơn threshold, giữ nguyên để tránh mất context
        split_threshold = chunk_size * 1.5  # Chỉ chia khi > 1200 chars (với chunk_size=800)
        min_chunk_size = 100  # Không tạo chunks nhỏ hơn 100 chars
        
        if len(content) > split_threshold:
            sub_chunks = splitter.split_text(content)
            for sub_chunk in sub_chunks:
                if sub_chunk.strip() and len(sub_chunk.strip()) >= min_chunk_size:
                    result.append({
                        "content": sub_chunk,
                        "metadata": {
                            **metadata,  # Giữ nguyên metadata (page, section)
                            "chunk_index": chunk_index,
                            "char_count": len(sub_chunk),
                        }
                    })
                    chunk_index += 1
        else:
            # Giữ nguyên chunk nếu không quá lớn
            result.append({
                "content": content,
                "metadata": {
                    **metadata,  # Giữ nguyên metadata
                    "chunk_index": chunk_index,
                    "char_count": len(content),
                }
            })
            chunk_index += 1
    
    return result


def get_file_type_from_filename(filename: str) -> str:
    """Lấy loại file từ extension."""
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    ext_map = {
        "pdf": "pdf",
        "docx": "docx",
        "doc": "docx",
        "md": "md",
        "markdown": "md",
        "txt": "txt",
    }
    return ext_map.get(ext, "txt")

