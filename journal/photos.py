from io import BytesIO
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
from django.core.exceptions import ValidationError

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_EDGE = 1600


def optimize_photo(upload):
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError('Each photo must be 12 MB or smaller.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(upload) as image:
                if image.format not in ('JPEG', 'PNG', 'WEBP'):
                    raise ValidationError('Use JPEG, PNG, or WebP photos.')
                if image.width * image.height > MAX_PIXELS:
                    raise ValidationError('Photos must be 40 megapixels or smaller.')
                if getattr(image, 'is_animated', False):
                    raise ValidationError('Choose a still photo rather than an animation.')
                image.load()
                oriented = ImageOps.exif_transpose(image)
                oriented.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
                # Flatten transparency on white and copy pixels into a fresh image.
                # Re-encoding never copies the original EXIF/GPS or embedded metadata.
                rgba = oriented.convert('RGBA')
                clean = Image.new('RGB', rgba.size, 'white')
                clean.paste(rgba, mask=rgba.getchannel('A'))
                output = BytesIO()
                quality = 82
                while True:
                    output.seek(0)
                    output.truncate()
                    clean.save(output, format='JPEG', quality=quality, optimize=True)
                    if output.tell() <= 512 * 1024:
                        break
                    if quality > 55:
                        quality -= 9
                    else:
                        clean.thumbnail((max(1, clean.width * 3 // 4), max(1, clean.height * 3 // 4)))
                return {'content': output.getvalue(), 'width': clean.width, 'height': clean.height}
    except ValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValidationError('This photo could not be read. Use a valid JPEG, PNG, or WebP image.')
    finally:
        upload.seek(0)
