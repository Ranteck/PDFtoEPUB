import os
import json
from openai import OpenAI

class LayoutRefinerLLM:
    def __init__(self, api_key: str = None):
        if api_key is None:
            api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY environment variable or pass as argument.")
        self.client = OpenAI(api_key=api_key, timeout=120.0)  # Increased timeout
        self.model_name = "gpt-4o-mini"

    def _build_system_prompt(self) -> str:
        return """
You are an expert XHTML 5 generator. Your task is to convert a JSON representation of a PDF page's layout into a single XHTML fragment suitable for an EPUB page.

**Input JSON Format:**
The input will be a JSON object string with the following structure:
{
  "page_width": <float>, // Page width in points
  "page_height": <float>, // Page height in points
  "page_number": <int>, // Current page number
  "elements": [
    {
      "type": "text", // or "image"
      "bbox": [<float_x0>, <float_y0>, <float_x1>, <float_y1>], // Bounding box in points, origin top-left of the PDF page
      "text": "<string_content>", // Only for "text" type, may contain newlines
      "attributes": { // Optional attributes for text elements
        "font_name": "<string>", // e.g., "Helvetica-Bold"
        "font_size": <float>, // Font size in points
        "color": "<hex_color_string>" // e.g., "#000000"
      }
    },
    {
      "type": "image",
      "bbox": [<float_x0>, <float_y0>, <float_x1>, <float_y1>],
      "image_path": "<string_relative_path_to_image>" // Relative path for use in <img> src
    }
    // ... more elements
  ]
}

**Output XHTML 5 Fragment Requirements:**

1.  **Overall Structure:**
    *   The output MUST be a single `<div>` element. This div acts as the page container.
    *   Assign this container div a class, for example, `epub-page-container`.
    *   The container's inline style MUST define its `width` and `height` using the input `page_width` and `page_height` in points (pt).
    *   Set `position: relative;` on this container div. For testing visibility, you can add `background-color: #f0f0f0;` but remove it for final output if not needed.

2.  **Content Area and Margins:**
    *   All content elements (text, images) must be placed considering the following page margins:
        *   Top margin: 72pt
        *   Left margin: 72pt
        *   Right margin: 72pt
        *   Bottom margin: 60pt
    *   The `bbox` coordinates in the input JSON are relative to the full PDF page dimensions (origin at top-left). You MUST adjust these coordinates for the XHTML elements to be positioned relative to the *content area's* top-left corner.
        *   The content area starts at `(72pt, 72pt)` from the container's top-left.

3.  **Element Styling (Absolute Positioning):**
    *   You will iterate through each object in the `elements` array provided in the input JSON. For *each* element object, you will generate exactly one corresponding `<div>` styled and positioned according to its `type` and `bbox` as detailed below.
    *   These element `<div>`s MUST use `position: absolute;`.
    *   Calculate `top`, `left`, `width`, and `height` CSS properties for these divs based on the element's `bbox` and adjusted for the page margins:
        *   `left = element_bbox[0] - 72` (in pt)
        *   `top = element_bbox[1] - 72` (in pt)
        *   `width = element_bbox[2] - element_bbox[0]` (in pt)
        *   `height = element_bbox[3] - element_bbox[1]` (in pt)
    *   Ensure units (`pt`) are specified for all CSS positioning and dimension properties.
*   IMPORTANT: Apart from the main page container `div`, the `div`s for each item in the `elements` array, and the `div` for the page number, do NOT generate any other `div` elements. Specifically, do not generate repetitive, empty, or zero-dimension `div`s that do not directly correspond to an input element or the specified page furniture.

4.  **Text Elements:**
    *   For elements with `type: "text"`:
        *   Place the text content directly inside its positioned `<div>`.
        *   Preserve all line breaks (`\n`) from the input `text` field. Use `white-space: pre-wrap;` style on the text container `<div>`.
        *   If `attributes` like `font_name`, `font_size`, and `color` are provided in the JSON, apply them using inline CSS styles to the text container `<div>`. Example: `font-family: '{{font_name}}'; font-size: {{font_size}}pt; color: {{color}};`. Handle missing attributes gracefully (i.e., don't apply style if attribute is not present).

5.  **Image Elements:**
    *   For elements with `type: "image"`:
        *   Place an `<img>` tag inside its positioned `<div>`.
        *   The `src` attribute of the `<img>` tag must be the `image_path` from the JSON.
        *   The `alt` attribute should be descriptive, e.g., "Image from page {{page_number}}".
        *   The `<img>` tag should fill its container `<div>`. Apply `style="width: 100%; height: 100%; object-fit: fill;"` to the `<img>` tag.

6.  **Page Number:**
    *   Include a page number display.
    *   Create a separate `<div>` for the page number, e.g., with class `page-number`.
    *   Style this `<div>` with `position: absolute; bottom: 30pt; right: 30pt; text-align: right; font-size: 8pt; color: #555555;`.
    *   The content of this `<div>` should be the `page_number` from the input JSON.

7.  **XHTML Validity:**
    *   Ensure all tags are correctly closed (e.g., `<br />` if you were to use it, though `pre-wrap` is preferred for text blocks).
    *   Use lowercase for tags and attributes.
    *   Attribute values must be enclosed in double quotes.
    *   The entire output must be a single, well-formed XHTML fragment starting with the container `<div>`.
    *   Do not include `<html>`, `<head>`, or `<body>` tags. Only the page container `<div>` and its contents.
"""

    def refine_layout(self, page_elements_json: list, page_width: float, page_height: float, page_number: int) -> str:
        user_content_payload = {
            "page_width": page_width,
            "page_height": page_height,
            "page_number": page_number,
            "elements": page_elements_json
        }
        
        user_message_json_str = json.dumps(user_content_payload, indent=2)
        print("[LayoutRefinerLLM] Preparing to call OpenAI API...")
        try:
            print(f"[LayoutRefinerLLM] Calling model: {self.model_name} with temperature 0.1")
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    {"role": "user", "content": user_message_json_str}
                ],
                temperature=0.1, # Lower temperature for more deterministic output
            )
            print("[LayoutRefinerLLM] OpenAI API call successful.")
            refined_xhtml = completion.choices[0].message.content
            print(f"[LayoutRefinerLLM] Raw XHTML from API:\n---\n{refined_xhtml}\n---")
            # The LLM might wrap the output in ```xhtml ... ```, so we need to strip that.
            if refined_xhtml.startswith("```xhtml\n"):
                refined_xhtml = refined_xhtml[len("```xhtml\n"):]
            if refined_xhtml.endswith("\n```"):
                refined_xhtml = refined_xhtml[:-len("\n```")]
            print("[LayoutRefinerLLM] XHTML stripped and ready to return.")
            return refined_xhtml.strip()
        except Exception as e:
            print(f"[LayoutRefinerLLM] Error calling OpenAI API: {e}")
            # In a real scenario, you might want to raise the exception or handle it more gracefully
            return f"<div style='color:red;'>Error generating XHTML: {e}</div>"

if __name__ == '__main__':
    import sys

    class Tee:
        def __init__(self, *files):
            self.files = files
        def write(self, obj):
            for f in self.files:
                f.write(obj)
                f.flush()
        def flush(self):
            for f in self.files:
                f.flush()

    log_file_path = "script_run.log"
    log_file_handle = None
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    try:
        log_file_handle = open(log_file_path, "w", encoding="utf-8")
        sys.stdout = Tee(original_stdout, log_file_handle)
        sys.stderr = Tee(original_stderr, log_file_handle)
        
        print("Testing LayoutRefinerLLM...")
        # Main test logic is now directly within the primary try block
        refiner = LayoutRefinerLLM()
        
        # Sample data (mimicking what Docling might output for a page)
        sample_page_width = 612  # 8.5 inches
        sample_page_height = 792 # 11 inches
        sample_page_num = 1
        sample_elements = [
            {
                "type": "text",
                "bbox": [72, 72, 300, 100],
                "text": "Hello World!\nThis is a test.",
                "attributes": {
                    "font_name": "Arial",
                    "font_size": 12,
                    "color": "#333333"
                }
            },
            {
                "type": "image",
                "bbox": [72, 120, 272, 320],
                "image_path": "images/sample_image.png"
            },
            {
                "type": "text",
                "bbox": [320, 72, 540, 100],
                "text": "Another text block on the right.",
                "attributes": {
                    "font_name": "Times New Roman",
                    "font_size": 10,
                    "color": "#0000FF"
                }
            }
        ]
        user_content_payload_for_print = {'page_width': sample_page_width, 'page_height': sample_page_height, 'page_number': sample_page_num, 'elements': sample_elements}
        print(f"Sending following JSON to LLM (via user message):\n{json.dumps(user_content_payload_for_print, indent=2)}")
        print("[MainTestBlock] Calling refiner.refine_layout...")
        xhtml_output = refiner.refine_layout(sample_elements, sample_page_width, sample_page_height, sample_page_num)
        print(f"[MainTestBlock] Received XHTML output from refine_layout. Length: {len(xhtml_output) if xhtml_output else 'N/A'}")
        
        output_filename = "test_layout_output.xhtml"
        print(f"[MainTestBlock] Attempting to save output to {output_filename}...")
        try:
            with open(output_filename, "w", encoding="utf-8") as f:
                f.write(xhtml_output)
            print(f"\n--- LLM Output (XHTML Fragment) saved to {output_filename} ---")
        except IOError as e:
            print(f"\n--- Error saving LLM Output to file: {e} ---")
            print("\n--- LLM Output (XHTML Fragment) --- ")
            print(xhtml_output) # Fallback to printing if file save fails

        print("\n--- End of Test ---")

    except ValueError as ve:
        print(f"Configuration Error: {ve}")
    except Exception as e:
        print(f"An unexpected error occurred during testing: {e}")

    finally:
        # Restore stdout and stderr and close log file
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        if log_file_handle:
            log_file_handle.close()
        # This final print goes only to the original console
        original_stdout.write(f"Full script log potentially saved to {log_file_path}\n")

