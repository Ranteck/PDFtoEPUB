import sys
import logging

original_stdout = getattr(sys, '__stdout__', sys.stdout)

stdout_handler = logging.StreamHandler(stream=original_stdout)
stdout_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
stdout_handler.setFormatter(formatter)
root_logger = logging.getLogger()
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)
root_logger.addHandler(stdout_handler)
root_logger.setLevel(logging.DEBUG)

effective_stdout = original_stdout

print("--- DEBUG: SCRIPT START (Testing docling.document_converter) ---", flush=True, file=effective_stdout)
logging.debug("--- ROOT LOGGER: SCRIPT START (Testing docling.document_converter) ---")

def main_test_docling_converter():
    print("--- PRINT: In main_test_docling_converter() - Before import attempt ---", flush=True, file=effective_stdout)
    logging.debug("--- ROOT LOGGER: In main_test_docling_converter() - Before import attempt ---")
    try:
        print("--- PRINT: Attempting 'import docling.document_converter' ---", flush=True, file=effective_stdout)
        logging.debug("--- ROOT LOGGER: Attempting 'import docling.document_converter' ---")
        import docling.document_converter
        print("--- PRINT: 'import docling.document_converter' SUCCEEDED ---", flush=True, file=effective_stdout)
        logging.debug("--- ROOT LOGGER: 'import docling.document_converter' SUCCEEDED ---")
        
        # Optionally, try to import the class itself
        # print("--- PRINT: Attempting 'from docling.document_converter import DocumentConverter' ---", flush=True, file=effective_stdout)
        # logging.debug("--- ROOT LOGGER: Attempting 'from docling.document_converter import DocumentConverter' ---")
        # from docling.document_converter import DocumentConverter
        # print("--- PRINT: 'from docling.document_converter import DocumentConverter' SUCCEEDED ---", flush=True, file=effective_stdout)
        # logging.debug("--- ROOT LOGGER: 'from docling.document_converter import DocumentConverter' SUCCEEDED ---")

    except ImportError as e_imp:
        print(f"--- PRINT: ImportError: {e_imp} ---", flush=True, file=effective_stdout)
        logging.error(f"--- ROOT LOGGER: ImportError: {e_imp} ---", exc_info=True)
    except Exception as e_gen:
        print(f"--- PRINT: Exception during docling.document_converter import: {e_gen} ---", flush=True, file=effective_stdout)
        logging.error(f"--- ROOT LOGGER: Exception during docling.document_converter import: {e_gen} ---", exc_info=True)
    else:
        print("--- PRINT: docling.document_converter import successful path completed ---", flush=True, file=effective_stdout)
        logging.debug("--- ROOT LOGGER: docling.document_converter import successful path completed ---")

if __name__ == '__main__':
    print("--- PRINT: In __main__ block, calling main_test_docling_converter() ---", flush=True, file=effective_stdout)
    logging.debug("--- ROOT LOGGER: In __main__ block, calling main_test_docling_converter() ---")
    main_test_docling_converter()
    print("--- PRINT: SCRIPT END (after main_test_docling_converter call) ---", flush=True, file=effective_stdout)
    logging.debug("--- ROOT LOGGER: SCRIPT END (after main_test_docling_converter call) ---")