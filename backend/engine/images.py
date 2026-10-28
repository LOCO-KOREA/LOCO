"""Shared EXIF-corrected RGB decoding for preview, inference and reports."""
def read_image(path):
    from PIL import Image, ImageOps
    with Image.open(path) as image: return ImageOps.exif_transpose(image).convert('RGB')
