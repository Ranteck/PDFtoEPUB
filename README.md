# PDF to EPUB Converter

This project provides a command line utility for turning a PDF document into an EPUB file. It relies on the `docling` toolkit for parsing the PDF and can optionally use the OpenAI API to refine page content into XHTML during the conversion.

## Requirements

- Python 3.10 or higher
- (Optional) an `OPENAI_API_KEY` environment variable if you want pages refined by the OpenAI API

## Installation

Install the project along with its dependencies using `pip` which reads from `pyproject.toml`:

```bash
pip install -e .
```

You can alternatively use another tool that understands `pyproject.toml` such as `uv`.

## Usage

Convert a PDF file to EPUB by running:

```bash
python pdf_to_epub.py --pdf_path path/to/document.pdf
```

By default the EPUB file is written next to the input PDF with the `.epub` extension. When the `OPENAI_API_KEY` is set, each page is processed through the API to improve the extracted text before packaging the EPUB.
