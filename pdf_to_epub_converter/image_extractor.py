import fitz  # PyMuPDF
import os
import io
from PIL import Image # For image format validation and conversion if necessary

class ImageExtractor:
    def __init__(self, output_image_folder: str = "OEBPS/Images"):
        self.output_image_folder = output_image_folder
        if not os.path.exists(self.output_image_folder):
            os.makedirs(self.output_image_folder, exist_ok=True)
        self.image_references = [] # To store mapping for XHTML embedding

    def _save_image(self, img_bytes: bytes, original_ext: str, page_num: int, img_index: int) -> (str, tuple):
        """
        Saves image bytes to a file, converting if necessary, and returns its path and dimensions.
        """
        filename_base = f"page{page_num}_img{img_index}"
        output_path = ""
        dimensions = (0,0)

        try:
            pil_image = Image.open(io.BytesIO(img_bytes))
            original_format = pil_image.format.upper()
            dimensions = pil_image.size

            # Prefer PNG for lossless, JPEG for photos if original was JPEG. SVG is handled separately.
            if original_format in ["JPEG", "JPG"]:
                save_format = "JPEG"
                ext = "jpg"
            elif original_format == "PNG":
                save_format = "PNG"
                ext = "png"
            else: # Convert other types to PNG for broad compatibility
                save_format = "PNG"
                ext = "png"
            
            output_filename = f"{filename_base}.{ext}"
            output_path = os.path.join(self.output_image_folder, output_filename)
            
            if pil_image.mode == 'P' and save_format == 'JPEG': # JPEG doesn't support paletted images well
                pil_image = pil_image.convert('RGB')

            pil_image.save(output_path, format=save_format, quality=95 if save_format=="JPEG" else None)
            print(f"Saved image: {output_path} (original format: {original_format}, saved as: {save_format})")
            return output_path, dimensions
        except Exception as e:
            print(f"Error saving image {filename_base} (original ext: {original_ext}): {e}")
            return None, None


    def extract_images_from_pdf(self, pdf_path: str) -> list:
        """
        Extracts images from all pages of a PDF.
        Returns a list of image reference details.
        """
        self.image_references = []
        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            print(f"Error opening PDF {pdf_path}: {e}")
            return []

        for page_num_idx, page in enumerate(doc):
            page_num_actual = page_num_idx + 1
            image_list = page.get_images(full=True)
            
            # Handling raster images
            for img_index, img_info in enumerate(image_list):
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                if not base_image:
                    continue

                img_bytes = base_image["image"]
                original_ext = base_image["ext"]
                
                # For SVG, PyMuPDF stores them differently.
                # We'll handle SVG extraction if we identify vector graphics.
                # This part focuses on raster images first.

                saved_path, dimensions = self._save_image(img_bytes, original_ext, page_num_actual, img_index)
                if saved_path:
                    self.image_references.append({
                        "original_xref": xref,
                        "page_number": page_num_actual,
                        "saved_path": os.path.relpath(saved_path, os.path.dirname(self.output_image_folder)).replace("\\", "/"), # Relative path for EPUB
                        "dimensions_px": dimensions, # (width, height)
                        "alt_text": f"Image from page {page_num_actual}, item {img_index + 1}" # Placeholder
                    })

            # Handling SVG (vector graphics)
            # PyMuPDF's get_drawings() can be used to extract vector graphics, potentially as SVG
            drawings = page.get_drawings()
            for drawing_index, drawing in enumerate(drawings):
                # This is a simplified approach. Real SVG extraction from drawings is complex.
                # PyMuPDF can output pages as SVG, which might be a better route if full vector is needed.
                # For now, we'll focus on embedded raster images.
                # If a drawing is a vector image that can be easily converted to SVG:
                if drawing["type"] == "f" and "svg" in drawing.get("path", "").lower(): # Example condition
                    # svg_data = ... # extract/convert drawing to SVG
                    # svg_filename = f"page{page_num_actual}_vec{drawing_index}.svg"
                    # svg_path = os.path.join(self.output_image_folder, svg_filename)
                    # with open(svg_path, "w") as f:
                    #     f.write(svg_data)
                    # self.image_references.append(...)
                    pass # Placeholder for more robust SVG handling

        doc.close()
        return self.image_references

    def get_image_references(self) -> list:
        return self.image_references

if __name__ == '__main__':
    # Example Usage (requires a test PDF with images)
    # Ensure you have a PDF named 'test.pdf' in the same directory or provide a full path.
    # And an 'OEBPS/Images' folder will be created if it doesn't exist.
    
    # Create a dummy requirements.txt to satisfy the script if it's not present
    if not os.path.exists("requirements.txt"):
        with open("requirements.txt", "w") as f:
            f.write("# Dummy requirements file\n")

    # Create a dummy PDF for testing if none exists
    dummy_pdf_path = "dummy_test_image_extraction.pdf"
    if not os.path.exists(dummy_pdf_path):
        try:
            doc = fitz.open()
            page = doc.new_page()
            # Try to add a tiny dummy image (e.g., a small black square using Pillow)
            try:
                img = Image.new('RGB', (10, 10), color = 'black')
                img_bytes_io = io.BytesIO()
                img.save(img_bytes_io, format='PNG')
                img_bytes = img_bytes_io.getvalue()
                rect = fitz.Rect(50, 50, 150, 150)
                page.insert_image(rect, stream=img_bytes)
                page.insert_text((50, 30), "Test PDF for Image Extractor")
            except Exception as e_img:
                print(f"Could not create dummy image for PDF: {e_img}")
                page.insert_text((50, 50), "Test PDF - No image could be embedded.")
            doc.save(dummy_pdf_path)
            doc.close()
            print(f"Created dummy PDF: {dummy_pdf_path}")
        except Exception as e_pdf:
            print(f"Could not create dummy PDF: {e_pdf}")
            dummy_pdf_path = None # Fallback if PDF creation fails

    if dummy_pdf_path and os.path.exists(dummy_pdf_path):
        print(f"Testing ImageExtractor with PDF: {dummy_pdf_path}")
        extractor = ImageExtractor(output_image_folder="OEBPS/Images_Test")
        references = extractor.extract_images_from_pdf(dummy_pdf_path)
        
        if references:
            print("\n--- Extracted Image References ---")
            for ref in references:
                print(ref)
        else:
            print("\nNo images extracted or an error occurred.")
        
        print(f"\nImages saved to: {os.path.abspath(extractor.output_image_folder)}")
    else:
        print("Skipping ImageExtractor test as no test PDF is available.")

