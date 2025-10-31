import os
from typing import Optional
from langchain.text_splitter import RecursiveCharacterTextSplitter


def parse_pdf(file_path: str) -> str:
    """Đọc nội dung từ file PDF."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
        return "\n".join(text_parts)
    except Exception as e:
        raise ValueError(f"Error parsing PDF: {str(e)}")


def parse_docx(file_path: str) -> str:
    """Đọc nội dung từ file DOCX."""
    try:
        from docx import Document
        doc = Document(file_path)
        paragraphs = [para.text for para in doc.paragraphs]
        return "\n".join(paragraphs)
    except Exception as e:
        raise ValueError(f"Error parsing DOCX: {str(e)}")


def parse_markdown(file_path: str) -> str:
    """Đọc nội dung từ file Markdown."""
    try:
        import mistune
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        # mistune có thể parse markdown, nhưng ở đây chỉ trả về text thô
        # Nếu muốn parse markdown thành HTML thì dùng: mistune.create_markdown()
        return content
    except Exception as e:
        raise ValueError(f"Error parsing Markdown: {str(e)}")


def parse_txt(file_path: str) -> str:
    """Đọc nội dung từ file TXT."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        raise ValueError(f"Error parsing TXT: {str(e)}")


def parse_file(file_path: str, file_type: str) -> str:
    """Parse file dựa trên loại file."""
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
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    separators: Optional[list[str]] = None,
) -> list[dict]:
    """Chia nhỏ text thành các chunks bằng LangChain RecursiveCharacterTextSplitter.
    
    Returns:
        list[dict]: Mỗi dict có format {"content": "...", "metadata": {...}}
    """
    if not text or not text.strip():
        return []
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators or ["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )
    
    chunks = splitter.split_text(text)
    result = []
    for idx, chunk in enumerate(chunks):
        result.append({
            "content": chunk,
            "metadata": {
                "chunk_index": idx,
                "char_count": len(chunk),
            },
        })
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

