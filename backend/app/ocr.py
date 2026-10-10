

import os
import io
import platform
from PIL import Image
import pytesseract
from dotenv import load_dotenv

load_dotenv()

# Configure Tesseract path — only needed on Windows where it's not on PATH
if platform.system() == "Windows":
    _TESSERACT_PATH = os.getenv("TESSERACT_PATH", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if os.path.exists(_TESSERACT_PATH):
        pytesseract.pytesseract.tesseract_cmd = _TESSERACT_PATH

def extract_text_from_image(image_bytes: bytes) -> str:
    """Extract raw text from an image using Tesseract OCR."""
    try:
        print("[OCR] Loading image...")
        image = Image.open(io.BytesIO(image_bytes))
        
        # Basic preprocessing for better OCR
        if image.mode != 'RGB':
            image = image.convert('RGB')
            
        print("[OCR] Running Tesseract...")
        text = pytesseract.image_to_string(image)
        print(f"[OCR] Extracted {len(text)} characters.")
        return text.strip()
    except Exception as e:
        print(f"[OCR] Error during extraction: {e}")
        return ""
