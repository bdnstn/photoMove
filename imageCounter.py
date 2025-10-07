import os
from datetime import datetime
from PIL import Image
from collections import defaultdict
import exifread
import pyheif
from io import BytesIO

def get_image_date(filepath):
    """Extract the date taken from an image's EXIF data or use file modification time as fallback."""
    try:
        if filepath.lower().endswith('.heic'):
            # Handle HEIC files
            heif_file = pyheif.read(filepath)
            for metadata in heif_file.metadata or []:
                if metadata.get('type') == 'Exif':
                    tags = exifread.process_file(BytesIO(metadata['data'][6:]), stop_tag='EXIF DateTimeOriginal')
                    if 'EXIF DateTimeOriginal' in tags:
                        date_str = str(tags['EXIF DateTimeOriginal'])
                        return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
        else:
            # Handle other image formats
            with open(filepath, 'rb') as f:
                tags = exifread.process_file(f, stop_tag='EXIF DateTimeOriginal')
                if 'EXIF DateTimeOriginal' in tags:
                    date_str = str(tags['EXIF DateTimeOriginal'])
                    return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
    except Exception:
        pass
    # Fallback to file modification time
    mtime = os.path.getmtime(filepath)
    return datetime.fromtimestamp(mtime)

def is_image_file(filename):
    """Check if a file is an image based on its extension."""
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.heic'}
    return os.path.splitext(filename.lower())[1] in image_extensions

def count_images_by_date(root_dir):
    """Walk the directory and count images grouped by year and month."""
    date_counts = defaultdict(lambda: defaultdict(int))
    
    for root, _, files in os.walk(root_dir):
        for filename in files:
            if is_image_file(filename):
                filepath = os.path.join(root, filename)
                try:
                    date = get_image_date(filepath)
                    year = date.year
                    month = date.strftime('%B')  # Full month name
                    date_counts[year][month] += 1
                except Exception as e:
                    print(f"Error processing {filepath}: {e}")
    
    return date_counts

def save_and_print_image_counts(date_counts, output_file):
    """Print the image counts and save to a file."""
    with open(output_file, 'w', encoding='utf-8') as f:
        for year in sorted(date_counts.keys()):
            year_line = f"\nYear {year}:\n"
            print(year_line.strip())
            f.write(year_line)
            for month in sorted(date_counts[year].keys()):
                month_line = f"  {month}: {date_counts[year][month]} images\n"
                print(month_line.strip())
                f.write(month_line)
        total_images = sum(sum(month_counts.values()) for month_counts in date_counts.values())
        total_line = f"\nTotal images found: {total_images}\n"
        print(total_line.strip())
        f.write(total_line)

def main():
    # Specify the directory to scan (modify as needed)
    root_dir = input("Enter the directory to scan for images: ").strip()
    if not os.path.isdir(root_dir):
        print("Invalid directory path!")
        return
    
    # Generate output filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"image_counts_{timestamp}.txt"
    
    print(f"Scanning directory: {root_dir}")
    date_counts = count_images_by_date(root_dir)
    print(f"Saving output to: {output_file}")
    save_and_print_image_counts(date_counts, output_file)

if __name__ == "__main__":
    main()