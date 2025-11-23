import os
import re
from typing import Optional, List, Dict
from langchain.text_splitter import RecursiveCharacterTextSplitter


def parse_pdf(file_path: str) -> List[Dict]:
    """Đọc PDF và trả về list chunks với page number VÀ section metadata."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        chunks = []
        current_section = None
        current_subsection = None  # THÊM: Track subsection
        
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text()
            if not text.strip():
                continue
            
            lines = text.split('\n')
            page_content_lines = []
            
            for line in lines:
                line_stripped = line.strip()
                if not line_stripped:
                    page_content_lines.append(line)
                    continue
                
                # CRITICAL FIX 1: Detect main sections (PHẦN, Chương)
                main_section_match = re.match(
                    r'^(PHẦN|Chương|CHƯƠNG|Phần|PART|Part)\s+(\d+)[:\s\-]?\s*(.*)$', 
                    line_stripped, 
                    re.IGNORECASE
                )
                
                if main_section_match:
                    section_type = main_section_match.group(1)
                    section_num = main_section_match.group(2)
                    section_title = main_section_match.group(3).strip()
                    
                    current_section = f"{section_type.upper()} {section_num}"
                    if section_title:
                        current_section += f": {section_title}"
                    
                    # Reset subsection khi gặp main section mới
                    current_subsection = None
                    
                    print(f"[Parser] 📍 Main section: {current_section} (page {page_num})")
                    
                    chunks.append({
                        "content": line_stripped,
                        "metadata": {
                            "page_number": page_num,
                            "section": current_section,
                            "heading": line_stripped,
                            "is_section_heading": True,
                            "is_main_section": True,
                            "file_type": "pdf"
                        }
                    })
                    continue
                
                # CRITICAL FIX 2: Detect subsections (8.1, 8.2, 7.1.2, etc.)
                subsection_match = re.match(
                    r'^(\d+\.\d+(?:\.\d+)?)[:\s\-]?\s*(.*)$',
                    line_stripped
                )
                
                if subsection_match:
                    subsection_num = subsection_match.group(1)
                    subsection_title = subsection_match.group(2).strip()
                    
                    current_subsection = subsection_num
                    if subsection_title:
                        current_subsection += f" {subsection_title}"
                    
                    print(f"[Parser]   📌 Subsection: {current_subsection} (page {page_num})")
                    
                    chunks.append({
                        "content": line_stripped,
                        "metadata": {
                            "page_number": page_num,
                            "section": current_section,  # Main section
                            "subsection": current_subsection,  # Subsection
                            "heading": line_stripped,
                            "is_subsection_heading": True,
                            "file_type": "pdf"
                        }
                    })
                    continue
                
                # CRITICAL FIX 3: Detect concept/topic headings
                # Pattern: Short lines (< 80 chars) ending with colon or all caps
                is_concept_heading = False
                concept_name = None
                
                if len(line_stripped) < 80:
                    # Pattern 1: "Arrow Function:" or "Hoisting:"
                    if line_stripped.endswith(':') and len(line_stripped.split()) <= 5:
                        is_concept_heading = True
                        concept_name = line_stripped.rstrip(':').strip()
                    
                    # Pattern 2: ALL CAPS short heading "ARROW FUNCTION"
                    elif line_stripped.isupper() and len(line_stripped.split()) <= 5:
                        is_concept_heading = True
                        concept_name = line_stripped
                    
                    # Pattern 3: Bold-like formatting "**Arrow Function**" (nếu có)
                    elif re.match(r'^\*{1,2}[A-Z][^*]+\*{1,2}$', line_stripped):
                        is_concept_heading = True
                        concept_name = line_stripped.strip('*').strip()
                
                if is_concept_heading and concept_name:
                    print(f"[Parser]     💡 Concept: {concept_name} (page {page_num})")
                    
                    chunks.append({
                        "content": line_stripped,
                        "metadata": {
                            "page_number": page_num,
                            "section": current_section,
                            "subsection": current_subsection,
                            "concept": concept_name,
                            "heading": line_stripped,
                            "is_concept_heading": True,
                            "file_type": "pdf"
                        }
                    })
                    continue
                
                # Regular line - add to page content
                page_content_lines.append(line)
            
            # Add page content với section/subsection hiện tại
            page_content = '\n'.join(page_content_lines).strip()
            if page_content:
                chunks.append({
                    "content": page_content,
                    "metadata": {
                        "page_number": page_num,
                        "section": current_section,
                        "subsection": current_subsection,
                        "file_type": "pdf"
                    }
                })
        
        doc.close()
        print(f"[Parser] ✅ Total chunks: {len(chunks)}")
        return chunks
    except Exception as e:
        raise ValueError(f"Error parsing PDF: {str(e)}")


def parse_docx(file_path: str) -> List[Dict]:
    """Đọc DOCX và detect headings/sections với better hierarchy."""
    try:
        from docx import Document
        doc = Document(file_path)
        chunks = []
        current_section = None
        current_subsection = None
        
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            
            # Detect heading styles
            if para.style.name.startswith('Heading'):
                level = int(para.style.name.replace('Heading ', '').split()[0])
                
                # Level 1 = main section
                if level == 1:
                    current_section = text
                    current_subsection = None
                    chunks.append({
                        "content": text,
                        "metadata": {
                            "section": current_section,
                            "heading": text,
                            "heading_level": level,
                            "is_section_heading": True,
                            "is_main_section": True,
                            "file_type": "docx"
                        }
                    })
                # Level 2 = subsection
                elif level == 2:
                    current_subsection = text
                    chunks.append({
                        "content": text,
                        "metadata": {
                            "section": current_section,
                            "subsection": current_subsection,
                            "heading": text,
                            "heading_level": level,
                            "is_subsection_heading": True,
                            "file_type": "docx"
                        }
                    })
                # Level 3+ = concept/topic
                else:
                    chunks.append({
                        "content": text,
                        "metadata": {
                            "section": current_section,
                            "subsection": current_subsection,
                            "concept": text,
                            "heading": text,
                            "heading_level": level,
                            "is_concept_heading": True,
                            "file_type": "docx"
                        }
                    })
            else:
                # CRITICAL: Detect inline headings (bold text patterns)
                # Check if text looks like a heading even without style
                is_inline_heading = False
                concept_name = None
                
                # Pattern: Short bold-like text ending with colon
                if len(text) < 80 and text.endswith(':'):
                    words = text.rstrip(':').split()
                    if len(words) <= 5 and words[0][0].isupper():
                        is_inline_heading = True
                        concept_name = text.rstrip(':').strip()
                
                # Pattern: Numbered subsection without style (e.g., "8.1 Arrow Function")
                subsection_match = re.match(r'^(\d+\.\d+(?:\.\d+)?)[:\s\-]?\s*(.*)$', text)
                if subsection_match:
                    subsection_num = subsection_match.group(1)
                    subsection_title = subsection_match.group(2).strip()
                    current_subsection = subsection_num
                    if subsection_title:
                        current_subsection += f" {subsection_title}"
                    
                    chunks.append({
                        "content": text,
                        "metadata": {
                            "section": current_section,
                            "subsection": current_subsection,
                            "heading": text,
                            "is_subsection_heading": True,
                            "file_type": "docx"
                        }
                    })
                    continue
                
                if is_inline_heading and concept_name:
                    chunks.append({
                        "content": text,
                        "metadata": {
                            "section": current_section,
                            "subsection": current_subsection,
                            "concept": concept_name,
                            "heading": text,
                            "is_concept_heading": True,
                            "file_type": "docx"
                        }
                    })
                else:
                    # Regular paragraph
                    chunks.append({
                        "content": text,
                        "metadata": {
                            "section": current_section,
                            "subsection": current_subsection,
                            "file_type": "docx"
                        }
                    })
        
        print(f"[Parser] ✅ Total chunks: {len(chunks)}")
        return chunks
    except Exception as e:
        raise ValueError(f"Error parsing DOCX: {str(e)}")


def parse_markdown(file_path: str) -> List[Dict]:
    """Đọc Markdown với better heading detection."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        chunks = []
        current_section = None
        current_subsection = None
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            
            # Detect markdown headings
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            if heading_match:
                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()
                
                # Level 1 = main section
                if level == 1:
                    current_section = heading_text
                    current_subsection = None
                    chunks.append({
                        "content": line,
                        "metadata": {
                            "section": current_section,
                            "heading": heading_text,
                            "heading_level": level,
                            "is_section_heading": True,
                            "is_main_section": True,
                            "file_type": "md"
                        }
                    })
                # Level 2 = subsection
                elif level == 2:
                    current_subsection = heading_text
                    chunks.append({
                        "content": line,
                        "metadata": {
                            "section": current_section,
                            "subsection": current_subsection,
                            "heading": heading_text,
                            "heading_level": level,
                            "is_subsection_heading": True,
                            "file_type": "md"
                        }
                    })
                # Level 3+ = concept
                else:
                    chunks.append({
                        "content": line,
                        "metadata": {
                            "section": current_section,
                            "subsection": current_subsection,
                            "concept": heading_text,
                            "heading": heading_text,
                            "heading_level": level,
                            "is_concept_heading": True,
                            "file_type": "md"
                        }
                    })
            else:
                chunks.append({
                    "content": line,
                    "metadata": {
                        "section": current_section,
                        "subsection": current_subsection,
                        "file_type": "md"
                    }
                })
        
        print(f"[Parser] ✅ Total chunks: {len(chunks)}")
        return chunks
    except Exception as e:
        raise ValueError(f"Error parsing Markdown: {str(e)}")


def parse_txt(file_path: str) -> List[Dict]:
    """Đọc TXT với better pattern detection."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        chunks = []
        current_section = None
        current_subsection = None
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            
            # Main section patterns
            main_section_match = re.match(
                r'^(PHẦN|Chương|Phần|CHƯƠNG|PART|Part)\s+\d+[:\s]',
                stripped,
                re.IGNORECASE
            )
            
            if main_section_match:
                current_section = stripped.rstrip(':').strip()
                current_subsection = None
                chunks.append({
                    "content": line,
                    "metadata": {
                        "section": current_section,
                        "heading": stripped,
                        "is_section_heading": True,
                        "is_main_section": True,
                        "file_type": "txt"
                    }
                })
                continue
            
            # Subsection patterns
            subsection_match = re.match(r'^(\d+\.\d+(?:\.\d+)?)[:\s]', stripped)
            if subsection_match:
                current_subsection = stripped.rstrip(':').strip()
                chunks.append({
                    "content": line,
                    "metadata": {
                        "section": current_section,
                        "subsection": current_subsection,
                        "heading": stripped,
                        "is_subsection_heading": True,
                        "file_type": "txt"
                    }
                })
                continue
            
            # ALL CAPS heading
            if stripped.isupper() and len(stripped) < 80 and len(stripped.split()) <= 5:
                chunks.append({
                    "content": line,
                    "metadata": {
                        "section": current_section,
                        "subsection": current_subsection,
                        "concept": stripped,
                        "heading": stripped,
                        "is_concept_heading": True,
                        "file_type": "txt"
                    }
                })
                continue
            
            # Regular content
            chunks.append({
                "content": line,
                "metadata": {
                    "section": current_section,
                    "subsection": current_subsection,
                    "file_type": "txt"
                }
            })
        
        print(f"[Parser] ✅ Total chunks: {len(chunks)}")
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
    """
    ENHANCED: Chia nhỏ chunks với smart metadata propagation.
    
    CRITICAL CHANGES:
    - Preserve section/subsection/concept through splits
    - Keep heading chunks intact (don't split)
    - Smarter chunk size thresholds
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
        
        # CRITICAL FIX: NEVER split heading chunks
        is_heading = (
            metadata.get("is_section_heading") or 
            metadata.get("is_subsection_heading") or 
            metadata.get("is_concept_heading")
        )
        
        if is_heading:
            # Keep headings intact, no splitting
            result.append({
                "content": content,
                "metadata": {
                    **metadata,
                    "chunk_index": chunk_index,
                    "char_count": len(content),
                }
            })
            chunk_index += 1
            continue
        
        # For content chunks, apply smart splitting
        split_threshold = chunk_size * 1.5
        min_chunk_size = 100
        
        if len(content) > split_threshold:
            sub_chunks = splitter.split_text(content)
            for sub_chunk in sub_chunks:
                if sub_chunk.strip() and len(sub_chunk.strip()) >= min_chunk_size:
                    result.append({
                        "content": sub_chunk,
                        "metadata": {
                            **metadata,  # Preserve ALL metadata (section, subsection, concept)
                            "chunk_index": chunk_index,
                            "char_count": len(sub_chunk),
                        }
                    })
                    chunk_index += 1
        else:
            # Keep chunk intact if not too large
            result.append({
                "content": content,
                "metadata": {
                    **metadata,
                    "chunk_index": chunk_index,
                    "char_count": len(content),
                }
            })
            chunk_index += 1
    
    print(f"[Parser] ✅ Split into {len(result)} final chunks")
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
