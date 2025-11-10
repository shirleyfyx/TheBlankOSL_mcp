import os
import tempfile
import pdfkit
from mcp.server.fastmcp import FastMCP
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import NameObject, BooleanObject
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph

mcp = FastMCP("pdf")

@mcp.tool()
def create_blank_pdf(output_path: str, num_pages: int = 1, width: float = 612, height: float = 792) -> str:
    """
    Creates a new blank PDF file.

    Args:
        output_path: Path to save the new PDF.
        num_pages: Number of blank pages to create (default 1).
        width: Page width in points (default 612 = letter width).
        height: Page height in points (default 792 = letter height).

    Returns:
        Success or error message.
    """
    try:
        writer = PdfWriter()
        for _ in range(num_pages):
            writer.add_blank_page(width, height)

        with open(output_path, "wb") as f:
            writer.write(f)

        return f"Successfully created blank PDF with {num_pages} page(s) at {output_path}"
    except Exception as e:
        return f"An error occurred: {e}"
    
@mcp.tool()
def create_pdf_from_html(output_path: str, html: str = None, url: str = None) -> str:
    """
    Creates a PDF from raw HTML content or a web page URL.

    Args:
        output_path: Path to save the PDF.
        html: Raw HTML content to render into PDF. (Optional)
        url: URL of a web page to convert to PDF. (Optional)

    Returns:
        Success or error message.
    """
    try:
        if not html and not url:
            return "Error: Provide either html content or a url."

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Convert HTML or URL to PDF
        if html:
            pdfkit.from_string(html, output_path)
        else:
            pdfkit.from_url(url, output_path)

        return f"PDF successfully created at {output_path}"
    except Exception as e:
        return f"An error occurred: {e}"
    
@mcp.tool()
def merge_pdfs(pdf_paths: list[str], output_path: str) -> str:
    """
    Merges multiple PDF files into a single PDF.

    Args:
        pdf_paths: List of paths to PDF files to merge.
        output_path: Path to save the merged PDF.

    Returns:
        Success or error message.
    """
    try:
        if not pdf_paths:
            return "Error: No PDF files provided to merge."

        writer = PdfWriter()

        for path in pdf_paths:
            if not os.path.exists(path):
                return f"Error: File not found: {path}"
            reader = PdfReader(path)
            for page in reader.pages:
                writer.add_page(page)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "wb") as f:
            writer.write(f)

        return f"Successfully merged {len(pdf_paths)} PDFs into {output_path}"
    except Exception as e:
        return f"An error occurred: {e}"
    
@mcp.tool()
def split_pdf(input_path: str, output_dir: str, page_ranges: list[tuple[int, int]] = None) -> str:
    """
    Splits a PDF into multiple PDFs.

    Args:
        input_path: Path to the input PDF.
        output_dir: Directory to save split PDFs.
        page_ranges: Optional list of tuples (start_page, end_page), 1-indexed.
                     If None, splits each page into a separate PDF.

    Returns:
        Success or error message.
    """
    try:
        if not os.path.exists(input_path):
            return f"Error: Input PDF does not exist: {input_path}"

        os.makedirs(output_dir, exist_ok=True)
        reader = PdfReader(input_path)
        total_pages = len(reader.pages)
        outputs = []

        # Split by page_ranges
        if page_ranges:
            for idx, (start, end) in enumerate(page_ranges, start=1):
                if start < 1 or end > total_pages or start > end:
                    return f"Error: Invalid page range ({start}, {end})"
                writer = PdfWriter()
                for page_num in range(start - 1, end):
                    writer.add_page(reader.pages[page_num])
                out_path = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(input_path))[0]}_part{idx}.pdf")
                with open(out_path, "wb") as f:
                    writer.write(f)
                outputs.append(out_path)
        else:  # Split every page
            for page_num, page in enumerate(reader.pages, start=1):
                writer = PdfWriter()
                writer.add_page(page)
                out_path = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(input_path))[0]}_page{page_num}.pdf")
                with open(out_path, "wb") as f:
                    writer.write(f)
                outputs.append(out_path)

        return f"Successfully split PDF into {len(outputs)} files in {output_dir}"
    except Exception as e:
        return f"An error occurred: {e}"
    
@mcp.tool()
def reorder_pages(input_path: str, output_path: str, new_order: list[int]) -> str:
    """
    Reorder pages in a PDF. Any page not included in `new_order` is deleted.

    Args:
        input_path: Path to the input PDF.
        output_path: Path to save the modified PDF.
        new_order: List of page numbers (1-indexed) in the desired order.

    Returns:
        Success or error message.
    """
    try:
        reader = PdfReader(input_path)
        writer = PdfWriter()
        total_pages = len(reader.pages)

        # Keep only valid pages
        final_order = [p for p in new_order if 1 <= p <= total_pages]

        for page_num in final_order:
            writer.add_page(reader.pages[page_num - 1])

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            writer.write(f)

        return f"PDF updated successfully: {output_path}"
    except Exception as e:
        return f"An error occurred: {e}"
    
@mcp.tool()
def rotate_pages(input_path: str, output_path: str, rotation: int, pages: list[int] = None) -> str:
    """
    Rotate pages in a PDF by 90, 180, or 270 degrees clockwise.

    Args:
        input_path: Path to the input PDF.
        output_path: Path to save the rotated PDF.
        rotation: Degrees to rotate (must be 90, 180, or 270).
        pages: List of page numbers (1-indexed) to rotate. If None, all pages are rotated.

    Returns:
        Success or error message.
    """
    try:
        if rotation not in (90, 180, 270):
            return "Error: rotation must be 90, 180, or 270 degrees."

        reader = PdfReader(input_path)
        writer = PdfWriter()
        total_pages = len(reader.pages)

        # Rotate pages
        for i, page in enumerate(reader.pages, start=1):
            if pages is None or i in pages:
                page.rotate(rotation)
            writer.add_page(page)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            writer.write(f)

        return f"PDF rotated successfully: {output_path}"
    except Exception as e:
        return f"An error occurred: {e}"
    
@mcp.tool()
def count_pages(pdf_path: str) -> int:
    """
    Counts the number of pages in a PDF.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Number of pages as an integer. Returns -1 if an error occurs.
    """
    try:
        if not os.path.exists(pdf_path):
            return -1

        reader = PdfReader(pdf_path)
        return len(reader.pages)
    except Exception:
        return -1
    
@mcp.tool()
def get_page_dimension(pdf_path: str, page_number: int = 1) -> tuple[float, float]:
    """
    Returns the width and height of a PDF page in points.

    Args:
        pdf_path: Path to the PDF file.
        page_number: Page number to check (1-indexed). Default is 1.

    Returns:
        Tuple (width, height) in points.
        Returns (-1, -1) if the PDF does not exist or page number is invalid.
    """
    try:
        if not os.path.exists(pdf_path):
            return -1, -1

        reader = PdfReader(pdf_path)
        if page_number < 1 or page_number > len(reader.pages):
            return -1, -1

        page = reader.pages[page_number - 1]
        media_box = page.mediabox
        width = float(media_box.width)
        height = float(media_box.height)
        return width, height
    except Exception:
        return -1, -1
    
@mcp.tool()
def extract_text(pdf_path: str, page_number: int) -> str:
    """
    Extracts text from a specific page in a PDF.

    Args:
        pdf_path: Path to the PDF file.
        page_number: Page number to extract (1-indexed).

    Returns:
        Extracted text as a string, or an empty string if page is invalid or has no text.
    """
    try:
        if not os.path.exists(pdf_path):
            return ""

        reader = PdfReader(pdf_path)
        if page_number < 1 or page_number > len(reader.pages):
            return ""

        page = reader.pages[page_number - 1]
        text = page.extract_text()
        return text or ""
    except Exception:
        return ""
    
@mcp.tool()
def add_text_to_page_wrapped(pdf_path: str, output_path: str, page_number: int, text: str,
                             x: float = 50, top_margin: float = 50,
                             font_name: str = "Times-Roman", font_size: int = 12) -> str:
    """
    Adds text to an existing PDF page, wrapping lines automatically, starting from top-left.

    Args:
        pdf_path: Input PDF file path.
        output_path: Output PDF file path.
        page_number: Page number to add text (1-indexed).
        text: Text to add.
        x: Distance from left edge (in points).
        top_margin: Distance from top edge (in points).
        font_name: Font name (default Times-Roman).
        font_size: Font size (default 12).

    Returns:
        Success or error message.
    """
    try:
        if not os.path.exists(pdf_path):
            return f"Error: PDF not found at {pdf_path}"

        reader = PdfReader(pdf_path)
        if page_number < 1 or page_number > len(reader.pages):
            return f"Error: Page number {page_number} is out of range"

        page_width = float(reader.pages[page_number - 1].mediabox.width)
        page_height = float(reader.pages[page_number - 1].mediabox.height)
        y = page_height - top_margin  # start from top-left

        # Create temporary PDF with wrapped text
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            c = canvas.Canvas(tmp_file.name, pagesize=(page_width, page_height))
            c.setFont(font_name, font_size)

            # Wrap text manually using Paragraph
            style = getSampleStyleSheet()['Normal']
            style.fontName = font_name
            style.fontSize = font_size
            para = Paragraph(text, style)

            max_width = page_width - x - 50  # leave 50 points margin on right
            para.wrapOn(c, max_width, page_height)
            para.drawOn(c, x, y)

            c.save()

            # Merge temporary PDF onto the target page
            stamp_reader = PdfReader(tmp_file.name)
            stamp_page = stamp_reader.pages[0]

            writer = PdfWriter()
            for i, page in enumerate(reader.pages, start=1):
                if i == page_number:
                    page.merge_page(stamp_page)
                writer.add_page(page)

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                writer.write(f)

        os.remove(tmp_file.name)
        return f"Text added successfully to page {page_number}: {output_path}"
    except Exception as e:
        return f"An error occurred: {e}"

@mcp.tool()
def add_image_to_page(pdf_path: str, output_path: str, page_number: int, image_path: str,
                      x: float = 50, top_margin: float = 50, width: float = None, height: float = None) -> str:
    """
    Adds an image to an existing PDF page.

    Args:
        pdf_path: Path to the input PDF.
        output_path: Path to save the updated PDF.
        page_number: Page number to add image (1-indexed).
        image_path: Path to the image file.
        x: Distance from left edge in points.
        top_margin: Distance from top edge in points.
        width: Desired width of the image in points (optional).
        height: Desired height of the image in points (optional).

    Returns:
        Success or error message.
    """
    try:
        if not os.path.exists(pdf_path):
            return f"Error: PDF not found at {pdf_path}"
        if not os.path.exists(image_path):
            return f"Error: Image not found at {image_path}"

        reader = PdfReader(pdf_path)
        if page_number < 1 or page_number > len(reader.pages):
            return f"Error: Page number {page_number} is out of range"

        page_width = float(reader.pages[page_number - 1].mediabox.width)
        page_height = float(reader.pages[page_number - 1].mediabox.height)
        y = page_height - top_margin  # start from top-left

        # Create temporary PDF with the image
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            c = canvas.Canvas(tmp_file.name, pagesize=(page_width, page_height))
            img = ImageReader(image_path)
            img_width, img_height = img.getSize()

            # Scale image if width or height is provided
            if width and height:
                img_width, img_height = width, height
            elif width:
                img_height = (width / img_width) * img_height
                img_width = width
            elif height:
                img_width = (height / img_height) * img_width
                img_height = height

            # Draw image at (x, y) with top-left alignment
            c.drawImage(img, x, y - img_height, width=img_width, height=img_height)
            c.save()

            # Merge temporary PDF onto the target page
            stamp_reader = PdfReader(tmp_file.name)
            stamp_page = stamp_reader.pages[0]

            writer = PdfWriter()
            for i, page in enumerate(reader.pages, start=1):
                if i == page_number:
                    page.merge_page(stamp_page)
                writer.add_page(page)

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                writer.write(f)

        os.remove(tmp_file.name)
        return f"Image added successfully to page {page_number}: {output_path}"
    except Exception as e:
        return f"An error occurred: {e}"


@mcp.tool()
def read_form_fields(pdf_path: str) -> dict:
    """
    Retrieves the form fields from a pdf to then be stored as a dictionary

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Dictionary of form fields: {field_name: value}
    """
    reader = PdfReader(pdf_path)
    return reader.get_fields()

@mcp.tool()
def fill_form_all_pages(input_pdf, output_pdf, data_dict):
    """
    Fills a PDF form, ensures all fields across all pages are visible, 
    and saves the new file.

    Args:
        input_pdf_path (str): The path to the template PDF form.
        output_pdf_path (str): The path where the filled PDF will be saved.
        form_data (dict): A dictionary where keys are the field names in the PDF 
                          and values are the data to input.
    """
    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    # 1. Add ALL pages from the reader to the writer
    # This loop ensures every page is available for processing
    for page in reader.pages:
        writer.add_page(page)

    # 2. Update form fields across ALL pages contained within the writer
    # The first argument 'writer.pages' refers to all pages we just added.
    # pypdf automatically handles finding the fields regardless of which page they are on.
    writer.update_page_form_field_values(
        writer.pages, data_dict
    )
    
    # 3. CRITICAL STEP FOR VISIBILITY:
    # Set the /NeedAppearances flag to True. 
    # This property is applied to the document catalog (AcroForm) level, 
    # affecting the entire document and all fields within it.
    writer.need_appearances = True 

    # 4. Write the output PDF
    with open(output_pdf, "wb") as output_file:
        writer.write(output_file)

if __name__ == "__main__":
    mcp.run(transport="stdio")
