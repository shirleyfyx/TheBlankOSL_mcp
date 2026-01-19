import anyio
import io
from typing import List, Tuple, Union, Dict, Any
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject
from mcp.server.fastmcp import FastMCP
from reportlab.pdfgen import canvas

# Initialize MCP Server
mcp = FastMCP("pdf_tools")

PathLike = Union[str, Path]

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _get_reader(path: Path) -> PdfReader:
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    return PdfReader(str(path))

# ---------------------------------------------------------------------
# PDF Tools
# ---------------------------------------------------------------------

@mcp.tool()
async def pdf_tools_count_pages(input_path: PathLike) -> int:
    """
    Get the total number of pages in a PDF.
    """
    path = Path(input_path).resolve()
    
    def _op():
        reader = _get_reader(path)
        return len(reader.pages)

    return await anyio.to_thread.run_sync(_op)


@mcp.tool()
async def pdf_tools_get_pages_dimension(
    pdf_path: PathLike, 
    pages: List[int]
) -> List[Tuple[float, float]]:
    """
    Get the width and height of specific pages.

    Args:
        pdf_path: Path to the PDF.
        pages: List of **0-based** page indices (e.g., [0, 2] for 1st and 3rd page).
    
    Returns:
        List of (width, height) tuples corresponding to the requested pages.
    """
    path = Path(pdf_path).resolve()

    def _op():
        reader = _get_reader(path)
        dimensions = []
        for page_num in pages:
            if page_num < 0 or page_num >= len(reader.pages):
                raise ValueError(f"Page index {page_num} out of range (0-{len(reader.pages)-1})")
            
            box = reader.pages[page_num].mediabox
            dimensions.append((float(box.width), float(box.height)))
        return dimensions

    return await anyio.to_thread.run_sync(_op)


@mcp.tool()
async def pdf_tools_insert_blank_pages(
    input_path: PathLike, 
    num_of_pages: int, 
    position: int, 
    width: float, 
    height: float, 
    output_path: PathLike
) -> str:
    """
    Insert blank pages into a PDF at a specific index.

    Args:
        position: The **0-based** index where pages will be inserted.
                  (0 = before first page, -1 = after last page).
        width: Width of the new blank pages.
        height: Height of the new blank pages.
    """
    in_path = Path(input_path).resolve()
    out_path = Path(output_path).resolve()

    def _op():
        reader = _get_reader(in_path)
        writer = PdfWriter()
        
        # Determine insertion index
        total_pages = len(reader.pages)
        insert_idx = position
        if insert_idx < 0:
            insert_idx = total_pages  # Append to end

        # 1. Add pages BEFORE insertion point
        for i in range(min(insert_idx, total_pages)):
            writer.add_page(reader.pages[i])

        # 2. Add BLANK pages
        for _ in range(num_of_pages):
            writer.add_blank_page(width=width, height=height)

        # 3. Add pages AFTER insertion point
        for i in range(insert_idx, total_pages):
            writer.add_page(reader.pages[i])

        with open(out_path, "wb") as f:
            writer.write(f)
        return str(out_path)

    return await anyio.to_thread.run_sync(_op)


@mcp.tool()
async def pdf_tools_merge_pages(input_paths: List[str], output_path: str) -> str:
    """
    Merge multiple PDF files into one.

    Args:
        input_paths: List of file paths to merge in order.
        output_path: Destination file path.
    """
    out_path = Path(output_path).resolve()
    src_paths = [Path(p).resolve() for p in input_paths]

    def _op():
        writer = PdfWriter()
        for src in src_paths:
            reader = _get_reader(src)
            writer.append(reader)
        
        with open(out_path, "wb") as f:
            writer.write(f)
        return str(out_path)

    return await anyio.to_thread.run_sync(_op)


@mcp.tool()
async def pdf_tools_split_pages(
    input_path: PathLike, 
    pages: List[int], 
    output_path: PathLike
) -> str:
    """
    Extract specific pages to create a new PDF.

    Args:
        pages: List of **0-based** page indices to extract.
    """
    in_path = Path(input_path).resolve()
    out_path = Path(output_path).resolve()

    def _op():
        reader = _get_reader(in_path)
        writer = PdfWriter()
        
        for page_num in pages:
            if 0 <= page_num < len(reader.pages):
                writer.add_page(reader.pages[page_num])
            else:
                raise ValueError(f"Page index {page_num} out of bounds")

        with open(out_path, "wb") as f:
            writer.write(f)
        return str(out_path)

    return await anyio.to_thread.run_sync(_op)


@mcp.tool()
async def pdf_tools_reorder_pages(input_path: PathLike, new_order: List[int], output_path: PathLike) -> str:
    """
    Create a new PDF by reordering the pages of the input.

    Args:
        new_order: List of **0-based** indices representing the new order.
                   Example: [2, 0, 1] moves page 3 to front.
        output_path: Path to save the reordered PDF.
    """
    in_path = Path(input_path).resolve()
    out_path = Path(output_path).resolve()

    def _op():
        reader = _get_reader(in_path)
        writer = PdfWriter()
        
        for index in new_order:
            if 0 <= index < len(reader.pages):
                writer.add_page(reader.pages[index])
            else:
                raise ValueError(f"Page index {index} out of bounds")

        with open(out_path, "wb") as f:
            writer.write(f)
        return str(out_path)

    return await anyio.to_thread.run_sync(_op)


@mcp.tool()
async def pdf_tools_rotate_pages(
    input_path: PathLike, 
    pages_and_rotation: List[Tuple[int, int]], 
    output_path: PathLike
) -> str:
    """
    Rotate specific pages in a PDF.

    Args:
        pages_and_rotation: List of tuples (page_index, degrees).
                            Degrees must be multiple of 90 (90, 180, 270, -90).
                            Page index is **0-based**.
    """
    in_path = Path(input_path).resolve()
    out_path = Path(output_path).resolve()

    def _op():
        reader = _get_reader(in_path)
        writer = PdfWriter()

        # Create a map for quick lookup: {page_index: rotation_angle}
        rot_map = {p: r for p, r in pages_and_rotation}

        for i, page in enumerate(reader.pages):
            if i in rot_map:
                # Rotate requires multiples of 90
                angle = rot_map[i]
                if angle % 90 != 0:
                   raise ValueError(f"Rotation angle {angle} must be a multiple of 90")
                page.rotate(angle)
            
            writer.add_page(page)

        with open(out_path, "wb") as f:
            writer.write(f)
        return str(out_path)

    return await anyio.to_thread.run_sync(_op)


@mcp.tool()
async def pdf_tools_extract_pages_text(
    pdf_path: PathLike, 
    pages: List[int]
) -> List[str]:
    """
    Extract text content from specific pages.

    Args:
        pages: List of **0-based** page indices.
    
    Returns:
        List of strings, where each string is the text of a requested page.
    """
    path = Path(pdf_path).resolve()

    def _op():
        reader = _get_reader(path)
        results = []
        for page_num in pages:
            if 0 <= page_num < len(reader.pages):
                text = reader.pages[page_num].extract_text()
                results.append(text)
            else:
                results.append(f"[Error: Page {page_num} out of bounds]")
        return results

    return await anyio.to_thread.run_sync(_op)

@mcp.tool()
async def pdf_tools_add_text_to_page(
    input_path: PathLike, 
    text: List[str], 
    position: Tuple[float, float], 
    font: str, 
    font_size: int, 
    page_num: int, 
    output_path: PathLike
) -> str:
    """
    Add text to a specific page.
    
    Args:
        text: List of strings. Each item starts on a new line.
              Text automatically wraps if it hits the right edge of the page.
        position: (x, y) coordinates. (0,0) is usually bottom-left.
        font: Standard PDF font name (e.g., 'Helvetica', 'Times-Roman', 'Courier').
        page_num: 0-based page index.
    """
    in_path = Path(input_path).resolve()
    out_path = Path(output_path).resolve()
    x_start, y_start = position

    def _op():
        # 1. Read existing PDF to get page dimensions
        reader = _get_reader(in_path)
        if page_num < 0 or page_num >= len(reader.pages):
            raise ValueError(f"Page {page_num} out of bounds.")
            
        page = reader.pages[page_num]
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)

        # 2. Create a temporary PDF "stamp" in memory using ReportLab
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(page_width, page_height))
        
        # Setup Font
        c.setFont(font, font_size)
        
        # Calculate available width (assuming 20px right margin)
        max_width = page_width - x_start - 20
        
        current_y = y_start
        line_height = font_size * 1.2

        # 3. Draw text with wrapping
        from reportlab.lib.utils import simpleSplit

        # Coordinate system note: PDF Y starts at bottom. 
        # If user assumes Y starts at top, we might need logic here. 
        # Standard PDF = (0,0) at bottom-left.
        
        for paragraph in text:
            # Wrap text if it exceeds width
            wrapped_lines = simpleSplit(paragraph, font, font_size, max_width)
            
            for line in wrapped_lines:
                # Check if we ran off the bottom of the page
                if current_y < 0:
                    break 
                c.drawString(x_start, current_y, line)
                current_y -= line_height  # Move down
            
            # Extra gap between paragraphs
            current_y -= (line_height * 0.5)

        c.save()
        packet.seek(0)

        # 4. Merge the stamp onto the original page
        stamp_pdf = PdfReader(packet)
        stamp_page = stamp_pdf.pages[0]
        
        writer = PdfWriter()
        
        # Copy all pages, merging the stamp only on the specific page
        for i, original_page in enumerate(reader.pages):
            if i == page_num:
                original_page.merge_page(stamp_page)
            writer.add_page(original_page)

        # 5. Write output
        with open(out_path, "wb") as f:
            writer.write(f)
            
        return str(out_path)

    return await anyio.to_thread.run_sync(_op)


@mcp.tool()
async def pdf_tools_add_image_to_page(
    input_path: PathLike, 
    image_path: PathLike, 
    position: Tuple[float, float], 
    page_num: int, 
    width: float,
    height: float,
    output_path: PathLike
) -> str:
    """
    Overlay an image onto a specific pdf page with optional resizing.

    Args:
        image_path: Path to the image file (JPG, PNG).
        position: (x, y) coordinates for the bottom-left corner.
        page_num: 0-based page index.
        width: The desired width of the image in PDF points.
               If provided without height, aspect ratio is preserved (if logic added).
               For now, this maps directly to ReportLab's width argument.
        height: The desired height of the image in PDF points.
    """
    in_path = Path(input_path).resolve()
    img_path = Path(image_path).resolve()
    out_path = Path(output_path).resolve()
    x, y = position

    if not img_path.exists():
        raise FileNotFoundError(f"Image not found: {img_path}")

    def _op():
        # 1. Read existing PDF
        reader = _get_reader(in_path)
        if page_num < 0 or page_num >= len(reader.pages):
            raise ValueError(f"Page {page_num} out of bounds.")
        
        page = reader.pages[page_num]
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)

        # 2. Create the image stamp
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(page_width, page_height))
        
        # ReportLab's drawImage accepts width and height.
        # If they are None, it uses the image's original size (at 72 DPI).
        # We also use mask='auto' to support transparent PNGs.
        c.drawImage(
            str(img_path), 
            x, 
            y, 
            width=width, 
            height=height, 
            mask='auto',
            preserveAspectRatio=True # Good practice if only one dim provided
        ) 
        
        c.save()
        packet.seek(0)

        # 3. Merge
        stamp_pdf = PdfReader(packet)
        stamp_page = stamp_pdf.pages[0]

        writer = PdfWriter()
        for i, original_page in enumerate(reader.pages):
            if i == page_num:
                original_page.merge_page(stamp_page)
            writer.add_page(original_page)

        # 4. Save
        with open(out_path, "wb") as f:
            writer.write(f)

        return str(out_path)

    return await anyio.to_thread.run_sync(_op)

@mcp.tool()
async def pdf_tools_extract_forms(input_path: PathLike) -> Dict[str, Any]:
    """
    Extract form field data from a PDF.
    
    Args:
        input_path: Path to the source PDF.
        output_path: Optional path to save the extracted schema as a JSON file.
                     If None, the data is just returned.
    """
    in_path = Path(input_path).resolve()

    def _op():
        # 1. Read PDF fields
        reader = PdfReader(in_path)
        fields = reader.get_fields() or {}

        # 2. Simplify the data (extract actual values from the raw PDF objects)
        extracted_data = {}
        for field_name, field_data in fields.items():
            # '/V' is the standard key for the value in PDF AcroForms
            # '/T' is the type, if needed
            current_value = field_data.get('/V', None)
            extracted_data[field_name] = current_value
        
        return extracted_data

    return await anyio.to_thread.run_sync(_op)


@mcp.tool()
async def pdf_tools_fill_forms(
    input_path: PathLike, 
    form_data: Dict[str, Any], 
    output_path: PathLike
) -> str:
    """
    Fill a PDF form with provided data.
    
    Args:
        input_path: Path to the source PDF with empty form fields.
        form_data: Dictionary where keys match PDF field names and values are the content to fill.
        output_path: Path where the filled PDF will be saved.
    """
    in_path = Path(input_path).resolve()
    out_path = Path(output_path).resolve()

    def _op():
        reader = PdfReader(in_path)
        writer = PdfWriter()

        # 1. Copy all pages to writer
        writer.append_pages_from_reader(reader)

        # --- FIX START: Explicitly copy the global AcroForm dictionary ---
        # This fixes the "No /AcroForm dictionary" error by manually linking 
        # the form definitions from the reader to the writer.
        if "/AcroForm" in reader.root_object:
            # We must verify the writer has a root object (it usually does after adding pages)
            # and then manually inject the AcroForm key.
            writer.root_object.update({
                NameObject("/AcroForm"): reader.root_object["/AcroForm"]
            })
        # --- FIX END ---

        # 2. Update form fields
        # Note: If a key in form_data doesn't exist in the PDF, pypdf simply ignores it.
        for page in writer.pages:
            writer.update_page_form_field_values(page, form_data)

        # 3. Write output
        with open(out_path, "wb") as f:
            writer.write(f)
            
        return str(out_path)

    return await anyio.to_thread.run_sync(_op)

if __name__ == "__main__":
    mcp.run(transport='stdio')
