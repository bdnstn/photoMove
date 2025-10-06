import os
from PIL import Image
from PIL.ExifTags import TAGS
from pathlib import Path
import time
from datetime import datetime
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_SUPPORT = True
except ImportError:
    HEIF_SUPPORT = False

def get_date_taken(filepath):
    """
    Extract 'Date Taken' from image EXIF data.
    Returns the date if found, None otherwise.
    """
    try:
        image = Image.open(filepath)
        
        # Method 1: Use getexif() - newer and more reliable
        if hasattr(image, 'getexif'):
            exif_data = image.getexif()
            if exif_data:
                # Try common EXIF tags for date taken
                # 36867 = DateTimeOriginal (preferred - when photo was taken)
                # 36868 = DateTimeDigitized (when photo was digitized)
                # 306 = DateTime (when file was last modified)
                for tag_id in [36867, 36868, 306]:
                    value = exif_data.get(tag_id)
                    # Make sure we got a string, not binary data
                    if value and isinstance(value, (str, bytes)):
                        if isinstance(value, bytes):
                            try:
                                value = value.decode('utf-8')
                            except:
                                continue
                        # Check if it looks like a date (not binary junk)
                        if value and ':' in value and len(value) >= 10:
                            return value
        
        # Method 2: Try _getexif() for older Pillow versions
        if hasattr(image, '_getexif'):
            exif_data = image._getexif()
            if exif_data and isinstance(exif_data, dict):
                for tag_id, value in exif_data.items():
                    tag_name = TAGS.get(tag_id, '')
                    if tag_name in ['DateTimeOriginal', 'DateTimeDigitized', 'DateTime']:
                        if isinstance(value, (str, bytes)):
                            if isinstance(value, bytes):
                                try:
                                    value = value.decode('utf-8')
                                except:
                                    continue
                            if value and ':' in value and len(value) >= 10:
                                return value
        
        return None
    except Exception as e:
        return None

def format_date_taken(date_str):
    """
    Format the date taken string for display.
    EXIF dates are typically in format: YYYY:MM:DD HH:MM:SS
    """
    if not date_str:
        return "No date"
    try:
        # Replace colons in date part with dashes for readability
        parts = str(date_str).split(' ')
        if len(parts) >= 2:
            date_part = parts[0].replace(':', '-')
            time_part = parts[1]
            return f"{date_part} {time_part}"
        return str(date_str)
    except:
        return str(date_str)

def scan_directory(directory_path):
    """
    Walk through directory structure and count files with/without date taken.
    """
    # Supported image extensions
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.heic', '.heif'}
    
    files_with_date = 0
    files_without_date = 0
    non_image_files = 0
    files_with_date_list = []
    files_without_date_list = []
    
    print(f"Scanning directory: {directory_path}\n")
    if not HEIF_SUPPORT:
        print("⚠ Warning: HEIC/HEIF support not available. Install pillow-heif for better results.")
        print("   Run: py -m pip install pillow-heif\n")
    print("Processing files...")
    
    for root, dirs, files in os.walk(directory_path):
        for filename in files:
            filepath = os.path.join(root, filename)
            file_ext = Path(filename).suffix.lower()
            
            # Check if it's an image file
            if file_ext in image_extensions:
                date_taken = get_date_taken(filepath)
                
                if date_taken:
                    files_with_date += 1
                    files_with_date_list.append((filepath, date_taken))
                else:
                    files_without_date += 1
                    files_without_date_list.append(filepath)
            else:
                non_image_files += 1
    
    return {
        'with_date': files_with_date,
        'without_date': files_without_date,
        'non_image': non_image_files,
        'with_date_list': files_with_date_list,
        'without_date_list': files_without_date_list
    }

def main():
    # Get directory path from user
    directory = input("Enter the directory path to scan: ").strip()
    
    # Remove quotes if user pasted a path with quotes
    directory = directory.strip('"').strip("'")
    
    if not os.path.exists(directory):
        print(f"Error: Directory '{directory}' does not exist.")
        return
    
    if not os.path.isdir(directory):
        print(f"Error: '{directory}' is not a directory.")
        return
    
    # Ask for output file name
    output_file = input("Enter output filename (default: scan_results.txt): ").strip()
    if not output_file:
        output_file = "scan_results.txt"
    
    # Start timing
    start_time = time.time()
    start_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Scan the directory
    results = scan_directory(directory)
    
    # Calculate elapsed time
    elapsed_time = time.time() - start_time
    minutes = int(elapsed_time // 60)
    seconds = elapsed_time % 60
    
    if minutes > 0:
        time_str = f"{minutes}m {seconds:.2f}s"
    else:
        time_str = f"{seconds:.2f}s"
    
    # Prepare output text
    output_lines = []
    output_lines.append("="*60)
    output_lines.append("SCAN RESULTS")
    output_lines.append("="*60)
    output_lines.append(f"Scan started:                {start_datetime}")
    output_lines.append(f"Scan duration:               {time_str}")
    output_lines.append(f"Scanned directory:           {directory}")
    output_lines.append(f"Files WITH 'Date Taken':     {results['with_date']}")
    output_lines.append(f"Files WITHOUT 'Date Taken':  {results['without_date']}")
    output_lines.append(f"Non-image files (skipped):   {results['non_image']}")
    output_lines.append(f"Total image files:           {results['with_date'] + results['without_date']}")
    output_lines.append("="*60)
    
    # Display results on screen
    for line in output_lines:
        print(line)
    
    # Ask if user wants to see detailed lists
    show_details = input("\nInclude detailed file lists in output? (y/n): ").strip().lower()
    
    if show_details == 'y':
        if results['with_date_list']:
            output_lines.append("\n--- Files WITH Date Taken ---")
            print("\n--- Files WITH Date Taken ---")
            for filepath, date_taken in results['with_date_list']:
                formatted_date = format_date_taken(date_taken)
                line = f"  ✓ [{formatted_date}] {filepath}"
                output_lines.append(line)
                print(line)
        
        if results['without_date_list']:
            output_lines.append("\n--- Files WITHOUT Date Taken ---")
            print("\n--- Files WITHOUT Date Taken ---")
            for f in results['without_date_list']:
                line = f"  ✗ {f}"
                output_lines.append(line)
                print(line)
    
    # Write to file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(output_lines))
        print(f"\n✓ Results saved to: {output_file}")
    except Exception as e:
        print(f"\n✗ Error saving file: {e}")

if __name__ == "__main__":
    main()