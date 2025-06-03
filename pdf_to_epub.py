import subprocess
import tempfile
from pathlib import Path
import json
import ebooklib
import argparse
import openai
import os # Added os module for environment variables
from docling.document_converter import DocumentConverter, PdfFormatOption # Added for PDF parsing
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling_core.types.doc import PictureItem # For image extraction
from PIL import Image # For saving images; docling might already provide PIL Images

def create_epub_directories():
    """Creates the basic directory structure for the EPUB in a temporary directory."""
    base_dir = Path(tempfile.mkdtemp())
    oebps_dir = base_dir / "OEBPS"
    text_dir = oebps_dir / "Text"
    images_dir = oebps_dir / "Images"
    styles_dir = oebps_dir / "Styles"

    text_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    styles_dir.mkdir(parents=True, exist_ok=True)

    return base_dir

# Placeholder for PDF parsing functions
def parse_pdf_to_layout_json(pdf_path: Path, work_dir: Path) -> tuple[DocumentConverter | None, dict]:
    """
    Parses the PDF file using DocumentConverter, saves its structure as layout.json,
    and returns the doc object and layout data.

    Args:
        pdf_path: Path to the input PDF file.
        work_dir: Directory to save the layout.json file.

    Returns:
        A tuple containing the docling document object and a dictionary of the PDF layout structure.
        Returns (None, {}) on failure.
    """
    try:
        # Configure pipeline options to ensure picture images are generated
        pipeline_options = PdfPipelineOptions()
        pipeline_options.generate_picture_images = True # Crucial for image extraction

        # Initialize DocumentConverter with these options
        # Assuming InputFormat.PDF exists in docling.datamodel.base_models (not explicitly imported here yet)
        # If InputFormat is not found, this line will need adjustment or further imports.
        # For now, proceeding with the structure from docling examples.
        try:
            from docling.datamodel.base_models import InputFormat # Attempting to import
        except ImportError:
            print("Warning: InputFormat could not be imported. PDF parsing might be configured incorrectly.")
            # Fallback or error, for now, let's assume it might work without explicit InputFormat if default
            converter = DocumentConverter()
        else:
            converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )

        # converter.convert() returns a ConversionResult object.
        # The actual DoclingDocument is in its 'document' attribute.
        conversion_result = converter.convert(str(pdf_path))

        if not conversion_result or not hasattr(conversion_result, 'document'):
            print("Error: PDF conversion did not return a valid document object.")
            return None, {}

        docling_document = conversion_result.document # This is the actual document model
        layout_data = docling_document.export_to_sexp() # Changed from export_structure()

        layout_json_path = work_dir / "layout.json"
        with open(layout_json_path, "w") as f:
            json.dump(layout_data, f, indent=2)

        print(f"PDF layout saved to: {layout_json_path}")
        # Return the DoclingDocument model, not the ConversionResult
        return docling_document, layout_data
    except Exception as e: # This will catch docling.api.errors.ConversionError too
        print(f"Error parsing PDF: {e}")
        return None, {}

# The 'doc_object' parameter below should be the DoclingDocument model
def extract_and_save_images(docling_document, layout_data: dict, images_output_dir: Path) -> dict:
    """
    Extracts images referenced in layout_data from the doc_object and saves them.

    Args:
        doc_object: The document object returned by DocumentConverter.convert().
        layout_data: The dictionary from doc_object.export_structure().
        images_output_dir: The directory (OEBPS/Images) to save extracted images.

    Returns:
        A dictionary mapping image reference names to their relative paths in the EPUB.
    """
    image_references = {}
    # Parameter renamed to docling_document for clarity
    if not docling_document or not hasattr(docling_document, 'pictures'):
        print("Warning: docling_document is None or does not have 'pictures' attribute. Skipping image extraction.")
        return image_references

    # Create a lookup for PictureItems by their self_ref
    picture_item_lookup = {}
    try:
        for pic_item in docling_document.pictures: # Use the passed DoclingDocument
            if isinstance(pic_item, PictureItem) and hasattr(pic_item, 'self_ref'):
                picture_item_lookup[pic_item.self_ref] = pic_item
            elif isinstance(pic_item, PictureItem) and hasattr(pic_item, 'get_ref'):
                 # Fallback if self_ref is not directly an attribute but accessible via get_ref().cref
                ref_obj = pic_item.get_ref()
                if ref_obj and hasattr(ref_obj, 'cref'):
                    picture_item_lookup[ref_obj.cref] = pic_item
    except Exception as e:
        print(f"Error building picture_item_lookup: {e}. Image extraction may be incomplete.")

    for page in layout_data.get('pages', []):
        for element in page.get('elements', []):
            if element.get('type') == 'image':
                img_ref = element.get('ref')
                if not img_ref:
                    continue

                picture_item = picture_item_lookup.get(img_ref)

                if picture_item:
                    try:
                        # Attempt to get the PIL image object
                        # Pass the DoclingDocument instance to get_image
                        pil_image = picture_item.get_image(docling_document)

                        if pil_image:
                            # Sanitize img_ref to create a valid filename, e.g., replace '#' and '/'
                            sanitized_ref = img_ref.replace("#/", "").replace("/", "_")
                            image_filename = f"{sanitized_ref}.png" # Assuming PNG, could check mimetype
                            image_save_path = images_output_dir / image_filename

                            pil_image.save(image_save_path, format="PNG")

                            # Path relative to OEBPS (parent of images_output_dir)
                            relative_path = image_save_path.relative_to(images_output_dir.parent)
                            image_references[img_ref] = str(relative_path)
                            print(f"Saved image: {img_ref} to {image_save_path}")
                        else:
                            print(f"Warning: Could not retrieve PIL image for {img_ref} from PictureItem.")
                    except AttributeError as ae:
                        print(f"AttributeError extracting image for {img_ref}: {ae}. PictureItem methods might be missing or doc_object is not as expected.")
                    except Exception as e:
                        print(f"Error processing image {img_ref}: {e}")
                else:
                    # This case means layout.json references an image that isn't in doc_object.pictures
                    # or the ref format doesn't match.
                    print(f"Warning: Image reference '{img_ref}' from layout_data not found in doc_object.pictures via self_ref.")
                    # Placeholder for trying to get image via PyMuPDF if docling fails or ref is different
                    # For now, just note it's missing.
                    # image_bytes = get_image_with_pymupdf(pdf_path, img_ref_details_from_layout)
                    # if image_bytes: ... save ...

    return image_references

# System prompt for LLM
SYSTEM_PROMPT = """\
You are an expert XHTML generator. Your task is to convert a JSON representation of a single page's content into a valid XHTML 1.1 document.
The JSON input contains a list of 'elements' such as 'text', 'heading', 'image', etc., each with a 'bbox' (bounding box) and other relevant properties.
Generate an XHTML file structured as follows:
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
<head>
    <title>Page Content</title>
    <link rel="stylesheet" type="text/css" href="../Styles/style.css" />
</head>
<body>
    <div class="page">
        <!-- Content will go here -->
    </div>
</body>
</html>

Rules for converting JSON elements to XHTML:
1.  **Text elements (`"type": "text"`)**: Wrap the content in `<p>` tags. Use the `text` field from the JSON element.
    Example JSON: `{"type": "text", "text": "Hello world", "bbox": [x, y, w, h]}`
    Example XHTML: `<p>Hello world</p>`
2.  **Heading elements (`"type": "heading"`)**: Wrap the content in `<h1>`, `<h2>`, etc., based on the `level` field. Default to `<h1>` if level is not specified. Use the `text` field.
    Example JSON: `{"type": "heading", "text": "Chapter 1", "level": 1, "bbox": [x, y, w, h]}`
    Example XHTML: `<h1>Chapter 1</h1>`
3.  **Image elements (`"type": "image"`)**: Use an `<img>` tag. The `ref` field in the JSON element will provide the image filename (e.g., "image1.png"). The `src` attribute should be `../Images/{{ref}}`. Add an `alt` attribute, which can be "Image {{ref}}".
    Example JSON: `{"type": "image", "ref": "image1.png", "bbox": [x, y, w, h]}`
    Example XHTML: `<img src="../Images/image1.png" alt="Image image1.png" />`
4.  **List elements (`"type": "list"`)**: These will contain `items`, each being a string. Convert to `<ul>` or `<ol>` (assume `<ul>` for now) and `<li>` for items.
    Example JSON: `{"type": "list", "items": ["Item 1", "Item 2"], "bbox": [x, y, w, h]}`
    Example XHTML: `<ul><li>Item 1</li><li>Item 2</li></ul>`
5.  **Other element types**: For any other element types, you can either attempt a reasonable generic representation (e.g., a `<p>` or `<div>` with the text content if available) or omit them if they don't map well to standard XHTML content. For now, try to represent them as a paragraph if they have a 'text' field, otherwise a div with their type.
6.  **Bounding Boxes (`bbox`)**: Bounding box information is for context and layout understanding by the system preparing data for you; you do not need to replicate bbox data as CSS or attributes in the XHTML. Focus on semantic structure.
7.  **Order**: Preserve the order of elements as they appear in the JSON `elements` array.
8.  **Valid XHTML 1.1**: Ensure the output is well-formed and valid XHTML 1.1. Pay attention to self-closing tags like `<img />` and `<link />`.
9.  **Encoding**: The XML declaration must specify UTF-8 encoding.

Process the following JSON data for one page and generate the complete XHTML file content:
"""

# Placeholder for LLM refinement functions
def refine_page_to_xhtml(page_data: dict, page_number: int, client: openai.OpenAI, work_dir: Path, image_references: dict) -> Path | None:
    """
    Refines a single page's layout data to XHTML using an LLM.

    Args:
        page_data: JSON dictionary for a single page from layout_data['pages'].
        page_number: The actual page number (1-indexed).
        client: An instance of openai.OpenAI.
        work_dir: The base working directory (where OEBPS is).
        image_references: Dictionary mapping original image refs to EPUB-relative paths.

    Returns:
        Path to the generated XHTML file, or None on failure.
    """
    import copy # For deepcopy

    page_data_for_llm = copy.deepcopy(page_data)

    # Update image refs in page_data_for_llm for the prompt
    # The LLM prompt expects {{ref}} to be the filename part, e.g., "image1.png"
    # and will construct <img src="../Images/{{ref}}"/>
    # image_references maps: original_ref -> "Images/new_filename.png"
    if 'elements' in page_data_for_llm:
        for element in page_data_for_llm['elements']:
            if element.get('type') == 'image':
                original_ref = element.get('ref')
                if original_ref and original_ref in image_references:
                    # image_references stores "Images/new_filename.png"
                    # We need to extract "new_filename.png" for the LLM prompt's {{ref}}
                    epub_image_path_str = image_references[original_ref]
                    # Use Path to easily get the filename
                    element['ref'] = Path(epub_image_path_str).name
                elif original_ref:
                    # If not in map, maybe it's already a filename or a placeholder?
                    # For safety, make it just the filename if it looks like a path.
                    element['ref'] = Path(original_ref).name
                    print(f"Warning: Image ref '{original_ref}' for page {page_number} not found in image_references map. Using filename directly: {element['ref']}")
                # If original_ref is None or empty, it will be handled by the LLM's generic rule or omitted.

    page_json_for_llm = json.dumps(page_data_for_llm, indent=2)
    full_prompt = f"{SYSTEM_PROMPT}\n\n{page_json_for_llm}"

    try:
        print(f"Sending page {page_number} data to LLM for XHTML conversion...")
        completion = client.chat.completions.create(
            model="gpt-4o-mini", # Consider making this configurable
            messages=[
                {"role": "system", "content": full_prompt}
                # Alternatively, can split:
                # {"role": "system", "content": SYSTEM_PROMPT},
                # {"role": "user", "content": page_json_for_llm}
            ]
        )

        xhtml_content = completion.choices[0].message.content
        if not xhtml_content:
            print(f"Error: LLM returned empty content for page {page_number}.")
            return None

        # Ensure the output is stripped of potential markdown backticks if LLM wraps it
        if xhtml_content.startswith("```xml"): # Or ```xhtml
            xhtml_content = xhtml_content[len("```xml"):]
            if xhtml_content.endswith("```"):
                xhtml_content = xhtml_content[:-len("```")]
        elif xhtml_content.startswith("```"): # Generic backtick
             xhtml_content = xhtml_content[len("```"):]
             if xhtml_content.endswith("```"):
                xhtml_content = xhtml_content[:-len("```")]
        xhtml_content = xhtml_content.strip()


    except openai.APIError as e:
        print(f"OpenAI API error for page {page_number}: {e}")
        return None
    except Exception as e:
        print(f"Error during LLM call for page {page_number}: {e}")
        return None

    text_dir = work_dir / "OEBPS" / "Text"
    text_dir.mkdir(parents=True, exist_ok=True) # Ensure Text directory exists
    xhtml_file_path = text_dir / f"page_{page_number:04d}.xhtml"

    try:
        with open(xhtml_file_path, "w", encoding="utf-8") as f:
            f.write(xhtml_content)
        print(f"Saved XHTML for page {page_number} to: {xhtml_file_path}")
        return xhtml_file_path
    except IOError as e:
        print(f"Error writing XHTML file for page {page_number} at {xhtml_file_path}: {e}")
        return None

# Placeholder for EPUB packaging functions
def create_global_stylesheet(stylesheet_path: Path) -> None:
    """
    Creates a global CSS stylesheet for the EPUB.

    Args:
        stylesheet_path: The full path where the style.css file will be saved.
    """
    css_content = """\
@page {
    margin-top: 72pt;
    margin-left: 72pt;
    margin-right: 72pt;
    margin-bottom: 60pt;
}

body {
    font-family: "Liberation Serif", serif; /* Example font, consider making this configurable or linked to extracted fonts */
    line-height: 1.4;
    text-align: justify;
}

h1, h2, h3, h4, h5, h6 {
    text-align: left;
    margin-top: 1em;
    margin-bottom: 0.5em;
    line-height: 1.2;
}

p {
    margin-top: 0.5em;
    margin-bottom: 0.5em;
}

img {
    max-width: 100%;
    height: auto;
    display: block; /* Helps with centering if margins are applied */
    margin: 1em auto; /* Basic centering for images */
}

.page {
    /* Basic container for page content, can be expanded */
    padding: 0;
}

.page-number {
    position: absolute; /* This might not work as expected in all readers or without specific HTML structure */
    right: 36pt;
    bottom: 24pt;
    font-size: 8pt;
    text-align: right;
}

/* Placeholder for @font-face rules if font extraction is implemented */
/*
@font-face {
    font-family: 'ExtractedFontName';
    src: url('../Fonts/ExtractedFontFile.ttf') format('truetype');
    font-weight: normal;
    font-style: normal;
}
*/
"""
    try:
        # Ensure the parent directory (Styles) exists.
        # It should have been created by create_epub_directories, but this is a safeguard.
        stylesheet_path.parent.mkdir(parents=True, exist_ok=True)
        with open(stylesheet_path, "w", encoding="utf-8") as f:
            f.write(css_content)
        print(f"Global stylesheet created at: {stylesheet_path}")
    except IOError as e:
        print(f"Error writing stylesheet to {stylesheet_path}: {e}")

def get_image_media_type(image_filename: str) -> str:
    """Determines the media type for an image based on its extension."""
    ext = Path(image_filename).suffix.lower()
    if ext == ".jpg" or ext == ".jpeg":
        return "image/jpeg"
    elif ext == ".png":
        return "image/png"
    elif ext == ".gif":
        return "image/gif"
    elif ext == ".svg":
        return "image/svg+xml"
    else:
        return "application/octet-stream" # Fallback

def create_epub_file(
    epub_path: Path,
    title: str,
    language: str,
    identifier: str,
    xhtml_file_paths: list[Path], # Absolute paths to XHTML files in work_dir
    image_oebps_paths: list[str], # Paths relative to OEBPS (e.g., "Images/pic1.png")
    css_oebps_path: str,          # Path relative to OEBPS (e.g., "Styles/style.css")
    work_dir: Path
) -> None:
    """
    Creates an EPUB file from the generated XHTML, images, and CSS.
    """
    from ebooklib import epub # Import here to keep it localized if needed

    book = epub.EpubBook()
    book.set_title(title)
    book.set_language(language)
    book.set_identifier(identifier) # Should be a unique ID, e.g., ISBN or a UUID

    # Add CSS item
    # css_path_within_oebps is like "Styles/style.css"
    # Full path to read content: work_dir / "OEBPS" / css_path_within_oebps
    css_full_path = work_dir / "OEBPS" / css_oebps_path
    if css_full_path.exists():
        css_item = epub.EpubItem(
            uid="style_sheet",
            file_name=css_oebps_path, # Path within EPUB (relative to OEBPS)
            media_type="text/css",
            content=css_full_path.read_bytes()
        )
        book.add_item(css_item)
    else:
        print(f"Warning: CSS file not found at {css_full_path}. EPUB will not include styles.")
        css_item = None # To avoid errors when linking

    # Add XHTML items and link CSS
    epub_xhtml_items = []
    for xhtml_file_path in xhtml_file_paths: # These are absolute paths
        # file_name for EpubHtml should be relative to OEBPS root, e.g., "Text/page_0001.xhtml"
        xhtml_oebps_filename = f"Text/{xhtml_file_path.name}"

        item = epub.EpubHtml(
            uid=xhtml_file_path.stem, # Unique ID for the item, e.g., "page_0001"
            file_name=xhtml_oebps_filename,
            title=xhtml_file_path.stem.replace("_", " ").title(), # Simple title from filename
            language=language
        )
        item.content = xhtml_file_path.read_bytes()

        if css_item: # Only add link if CSS item was successfully created
            # Relative path from Text/page.xhtml to Styles/style.css is ../Styles/style.css
            # css_oebps_path is "Styles/style.css"
            # So, Link href should be "../" + css_oebps_path
            item.add_link(epub.Link(href=f"../{css_oebps_path}", rel="stylesheet", type="text/css"))

        book.add_item(item)
        epub_xhtml_items.append(item)

    # Add Image items
    # image_oebps_paths contains paths like "Images/pic1.png"
    for img_oebps_path_str in image_oebps_paths:
        img_full_path = work_dir / "OEBPS" / img_oebps_path_str
        if img_full_path.exists():
            media_type = get_image_media_type(img_oebps_path_str)
            img_item = epub.EpubItem(
                uid=Path(img_oebps_path_str).stem, # Unique ID, e.g., "pic1"
                file_name=img_oebps_path_str,    # Path within EPUB (relative to OEBPS)
                media_type=media_type,
                content=img_full_path.read_bytes()
            )
            book.add_item(img_item)
        else:
            print(f"Warning: Image file not found at {img_full_path}. It will be missing from EPUB.")

    # Create Table of Contents (ToC)
    if epub_xhtml_items: # Ensure there are items for the ToC
        book.toc = tuple([epub.Link(item.file_name, item.title, item.uid) for item in epub_xhtml_items])
    else:
        book.toc = () # Empty ToC if no XHTML files
        print("Warning: No XHTML items to add to Table of Contents.")

    # Add NCX and Nav items (standard EPUB ToC files)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Define Spine (order of content reading)
    # 'nav' refers to the EpubNav item automatically created by ebooklib
    book.spine = ['nav'] + epub_xhtml_items
    if not epub_xhtml_items: # If only nav, some readers might complain or show blank.
        # Could add a dummy page or handle this case, but for now, it's as is.
        print("Warning: Spine contains only 'nav' as no XHTML content pages were added.")


    # Write EPUB file
    try:
        epub.write_epub(epub_path, book, {})
        print(f"EPUB successfully created at: {epub_path}")
    except Exception as e:
        print(f"Error writing EPUB file to {epub_path}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert a PDF file to EPUB format.")
    parser.add_argument(
        "--pdf_path",
        "-p",
        type=str,
        required=True,
        help="Path to the input PDF file."
    )
    parser.add_argument(
        "--output_epub_path",
        "-o",
        type=str,
        default=None,
        help="Path to save the output EPUB file. Defaults to '[pdf_filename].epub'."
    )
    args = parser.parse_args()

    cli_pdf_path = Path(args.pdf_path)

    if not cli_pdf_path.exists() or not cli_pdf_path.is_file():
        print(f"Error: PDF file not found at {cli_pdf_path}")
        exit(1)

    if args.output_epub_path:
        cli_output_epub_path = Path(args.output_epub_path)
    else:
        cli_output_epub_path = cli_pdf_path.with_suffix(".epub")

    if cli_output_epub_path.parent and not cli_output_epub_path.parent.exists():
        cli_output_epub_path.parent.mkdir(parents=True, exist_ok=True)

    work_dir = create_epub_directories()
    print(f"EPUB directory structure created at: {work_dir}")

    oebps_dir = work_dir / "OEBPS"
    images_dir = oebps_dir / "Images"
    styles_dir = oebps_dir / "Styles"

    doc_object_from_parse = None
    layout_json_data = {}
    image_references_map = {}
    xhtml_files = []

    openai_client = None
    if os.getenv("OPENAI_API_KEY"):
        try:
            openai_client = openai.OpenAI()
        except Exception as e:
            print(f"Failed to initialize OpenAI client: {e}. LLM refinement will be skipped.")
    else:
        print("Warning: OPENAI_API_KEY environment variable not set. LLM calls will be skipped.")

    stylesheet_save_path = styles_dir / "style.css"
    create_global_stylesheet(stylesheet_save_path)

    print(f"Attempting to parse PDF: {cli_pdf_path}")
    doc_object_from_parse, layout_json_data = parse_pdf_to_layout_json(cli_pdf_path, work_dir)

    if doc_object_from_parse and layout_json_data:
        print("PDF parsed and layout.json saved successfully.")

        print(f"Attempting to extract images to: {images_dir}")
        image_references_map = extract_and_save_images(doc_object_from_parse, layout_json_data, images_dir)

        if image_references_map:
            print("Image extraction attempt finished. References:")
            for ref, path_val in image_references_map.items():
                print(f"  {ref} -> {path_val}")
        else:
            print("No images were extracted or mapped.")

        if openai_client and layout_json_data.get('pages'):
            print("\nStarting LLM refinement for page content to XHTML...")
            pages_layout_data = layout_json_data.get('pages', [])
            for i, page_content_from_layout in enumerate(pages_layout_data):
                actual_page_number = page_content_from_layout.get('page_no', i + 1)

                xhtml_path = refine_page_to_xhtml(
                    page_content_from_layout, actual_page_number,
                    openai_client, work_dir, image_references_map
                )
                if xhtml_path:
                    xhtml_files.append(xhtml_path)

            if xhtml_files:
                print("\nGenerated XHTML files:")
                for xp in xhtml_files: print(f"  {xp}")
            else:
                print("No XHTML files were generated by the LLM process.")
        elif not openai_client:
            print("OpenAI client not available or API key not set. Skipping LLM refinement.")
        else:
            print("No page data available in layout_json_data for LLM refinement.")

        if xhtml_files:
            book_title_cli = cli_pdf_path.stem
            image_oebps_paths_list_cli = list(image_references_map.values())
            css_oebps_relative_path_cli = str(stylesheet_save_path.relative_to(oebps_dir))

            create_epub_file(
                epub_path=cli_output_epub_path,
                title=book_title_cli,
                language="en",
                identifier=f"urn:uuid:{book_title_cli}-{os.urandom(4).hex()}",
                xhtml_file_paths=xhtml_files,
                image_paths_within_oebps=image_oebps_paths_list_cli,
                css_path_within_oebps=css_oebps_relative_path_cli,
                work_dir=work_dir
            )
        else:
            print("No XHTML files were generated, skipping EPUB packaging.")
    else:
        print("PDF parsing failed or returned no data. Cannot proceed with EPUB generation.")

    # import shutil
    # if work_dir and work_dir.exists():
    #     try:
    #         # shutil.rmtree(work_dir)
    #         print(f"Temporary directory {work_dir} not removed for inspection.")
    #     except Exception as e:
    #         print(f"Error cleaning up temporary directory {work_dir}: {e}")
