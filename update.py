import os
import csv
import datetime
import subprocess
import uuid
from PIL import Image
from PIL.ExifTags import TAGS

# Base directory path
base_dir = "/mnt/user/Immich_Karina/29.03.2026"

def parse_date(date_str):
    try:
        return datetime.datetime.strptime(date_str, '%A %B %d,%Y %I:%M %p GMT')
    except Exception:
        return None

def get_exif_datetimeoriginal(filepath, exif_cache):
    """Retrieve EXIF DateTimeOriginal, using cache if available."""
    if filepath in exif_cache:
        return exif_cache[filepath]
    try:
        image = Image.open(filepath)
        exif_data = image._getexif()
        if exif_data:
            for tag_id, value in exif_data.items():
                if TAGS.get(tag_id) == 'DateTimeOriginal':
                    dt = datetime.datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                    exif_cache[filepath] = dt
                    return dt
        exif_cache[filepath] = None
        return None
    except Exception:
        exif_cache[filepath] = None
        return None

def set_exif_datetimeoriginal(filepath, date_obj):
    try:
        subprocess.run([
            'exiftool',
            '-DateTimeOriginal=' + date_obj.strftime('%Y:%m:%d %H:%M:%S'),
            '-overwrite_original',
            filepath
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to set EXIF for {filepath}: {e}")

for root, dirs, files in os.walk(base_dir):
    if os.path.basename(root) != "Photos":
        continue

    # Load CSV data once per folder
    csv_files = [f for f in files if f.lower().endswith('.csv')]
    csv_data = {}
    for csv_file in csv_files:
        csv_path = os.path.join(root, csv_file)
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)
            try:
                img_name_idx = headers.index('imgName')
                date_idx = headers.index('originalCreationDate')
                import_date_idx = headers.index('importDate')
            except ValueError:
                continue
            for row in reader:
                filename = row[img_name_idx]
                original_date_str = row[date_idx]
                import_date_str = row[import_date_idx]
                original_date = parse_date(original_date_str) if original_date_str else None
                import_date = parse_date(import_date_str) if import_date_str else None
                csv_data[filename] = {
                    'original_date': original_date,
                    'import_date': import_date
                }

    # Cache for EXIF data
    exif_cache = {}

    # Process media files after CSV load
    for media_file in os.listdir(root):
        media_path = os.path.join(root, media_file)
        if not os.path.isfile(media_path):
            continue
        if media_file.lower().endswith('.csv'):
            continue

        print(f"\nProcessing {media_file}")

        # Get EXIF DateTimeOriginal (cached)
        exif_date = get_exif_datetimeoriginal(media_path, exif_cache)

        # Determine date to use
        if exif_date:
            date_to_use = exif_date
        else:
            info = csv_data.get(media_file)
            if info:
                date_to_use = info['original_date'] or info['import_date']
            else:
                print(f"No date info for {media_file}, skipping.")
                continue

        # Update filesystem timestamps
        ts = date_to_use.timestamp()
        os.utime(media_path, (ts, ts))
        # Update EXIF data
        set_exif_datetimeoriginal(media_path, date_to_use)

        # Rename file
        date_str_filename = date_to_use.strftime('%Y-%m-%d_%H%M')
        ext = os.path.splitext(media_file)[1]
        unique_id = uuid.uuid4().hex[:4]
        new_name = f"{date_str_filename}_{unique_id}{ext}"
        new_path = os.path.join(root, new_name)
        os.rename(media_path, new_path)
        print(f"Renamed to {new_name}")
