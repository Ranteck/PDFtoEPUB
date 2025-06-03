import os
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

def create_dummy_pdf():
    """Creates a simple dummy PDF in the data/ directory."""
    project_root = Path(__file__).parent
    data_dir = project_root / "data"
    pdf_path = data_dir / "dummy.pdf"

    # Ensure data directory exists
    data_dir.mkdir(parents=True, exist_ok=True)

    # Create a new PDF with Reportlab
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    width, height = letter

    # Add a title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, height - 100, "Dummy PDF for Docling Testing")

    # Add some simple text
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 150, "Hello Docling!")
    c.drawString(100, height - 170, "This is a simple PDF document created by a script.")
    c.drawString(100, height - 190, "It contains one page with a few lines of text.")

    c.showPage()
    c.save()

    print(f"Successfully created dummy PDF: {pdf_path.resolve()}")

if __name__ == "__main__":
    create_dummy_pdf()
