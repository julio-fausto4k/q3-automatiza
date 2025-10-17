"""Image processing and optimization utilities."""
from io import BytesIO
from typing import Tuple, Union
from PIL import Image

def optimize_image(
    file_bytes: bytes, 
    max_size: Tuple[int, int] = (800, 600), 
    quality: int = 85
) -> bytes:
    """Resize and compress image before upload."""
    try:
        img = Image.open(BytesIO(file_bytes))
        
        # Resize maintaining aspect ratio
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Convert RGBA to RGB if needed
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                background.paste(img, mask=img.split()[-1])
            else:
                background.paste(img)
            img = background
        
        # Compress
        output = BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        return output.getvalue()
    except Exception as e:
        print(f"⚠️ Error optimizing image: {e}")
        return file_bytes  # Return original if optimization fails

def get_image_dimensions(file_bytes: bytes) -> Tuple[int, int]:
    """Get image dimensions from bytes."""
    try:
        img = Image.open(BytesIO(file_bytes))
        return img.size
    except Exception:
        return (0, 0)

def is_valid_image(file_bytes: bytes) -> bool:
    """Check if bytes represent a valid image."""
    try:
        Image.open(BytesIO(file_bytes))
        return True
    except Exception:
        return False
