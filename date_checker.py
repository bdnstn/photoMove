import os
from PIL import Image
from PIL.ExifTags import TAGS
from pathlib import Path
import time
from datetime import datetime
import re
import shutil
import warnings
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_SUPPORT = True
except ImportError:
    HEIF_SUPPORT = False

# Increase the decompression bomb limit or catch the warning
Image.MAX_IMAGE_PIXELS = None  # Remove limit entirely (or set to a higher value like 200000000)

def get_date_taken(filepath):
    """
    Extract 'Date Taken' from image EXIF data.
    Returns the date if found, None otherwise.
    Supports JPEG, TIFF, PNG, HEIC, and RAF (Fujifilm RAW).
    Raises exception with filepath if there's an error.
    """
    try:
        with Image.open(filepath) as image:
            # For RAF files, Pillow can read EXIF from the embedded JPEG preview
            if hasattr(image, 'getexif'):
                exif = image.getexif()
                if exif:
                    for tag_id, value in exif.items():
                        tag = TAGS.get(tag_id, tag_id)
                        if tag == 'DateTimeOriginal':
                            return value
            # Method 2: Try _getexif() for older Pillow versions
            if hasattr(image, '_getexif'):
                exif = image._getexif()
                if exif:
                    for tag_id, value in exif.items():
                        tag = TAGS.get(tag_id, tag_id)
                        if tag == 'DateTimeOriginal':
                            return value
            return None
    except Exception as e:
        # Re-raise with filepath info
        raise Exception(f"Error processing {filepath}: {str(e)}")

def extract_date_from_path(filepath):
    """
    Extract year and month from folder structure like photos\1997\04
    Returns tuple of (year, month) or (None, None)
    """
    try:
        # Get the path parts
        parts = Path(filepath).parts
        
        # Look for year\month pattern (YYYY\MM)
        for i in range(len(parts) - 1):
            # Check if this part looks like a year (4 digits, 1900-2099)
            year_match = re.match(r'^(19\d{2}|20\d{2})$', parts[i])
            if year_match and i + 1 < len(parts):
                # Check if next part looks like a month (01-12)
                month_match = re.match(r'^(0[1-9]|1[0-2])$', parts[i + 1])
                if month_match:
                    return (parts[i], parts[i + 1])
        
        return (None, None)
    except Exception:
        return (None, None)

def dates_match_folder(date_str, filepath):
    """
    Check if the date taken matches the year/month from folder structure.
    Returns True if they match, False if they don't, None if no folder date.
    """
    folder_year, folder_month = extract_date_from_path(filepath)
    
    if not folder_year or not folder_month:
        return None  # No folder structure to compare
    
    if not date_str:
        return None  # No date to compare
    
    try:
        # Extract year and month from date string (YYYY:MM:DD format)
        date_parts = str(date_str).split(':')
        if len(date_parts) >= 2:
            file_year = date_parts[0]
            file_month = date_parts[1]
            
            return file_year == folder_year and file_month == folder_month
    except:
        return None
    
    return None

def format_date_taken(date_str, from_folder=False):
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
            result = f"{date_part} {time_part}"
        else:
            result = str(date_str)
        
        # Add indicator if date came from folder
        if from_folder:
            result += " (from folder)"
        
        return result
    except:
        return str(date_str)

def scan_directory(directory_path):
    """
    Walk through directory structure and count files with/without date taken.
    """
    # Supported image extensions
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.heic', '.heif'}
    
    # Video extensions to skip
    video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.wmv', '.flv', '.webm', '.3gp'}
    
    files_with_date = 0
    files_without_date = 0
    files_with_folder_date = 0
    files_with_mismatched_date = 0
    non_image_files = 0
    video_files = 0
    error_files = 0
    warning_files = 0
    files_with_date_list = []
    files_without_date_list = []
    files_with_folder_date_list = []
    files_with_mismatched_date_list = []
    skipped_files_list = []
    video_files_list = []
    error_files_list = []
    warning_files_list = []
    
    print(f"Scanning directory: {directory_path}\n")
    if not HEIF_SUPPORT:
        print("⚠ Warning: HEIC/HEIF support not available. Install pillow-heif for better results.")
        print("   Run: py -m pip install pillow-heif\n")
    print("Processing files...")
    
    for root, dirs, files in os.walk(directory_path):
        for filename in files:
            filepath = os.path.join(root, filename)
            file_ext = Path(filename).suffix.lower()
            
            # Skip video files
            if file_ext in video_extensions:
                video_files += 1
                video_files_list.append(filepath)
                continue
            
            # Check if it's an image file
            if file_ext in image_extensions:
                try:
                    # Catch warnings (like DecompressionBombWarning)
                    with warnings.catch_warnings(record=True) as w:
                        warnings.simplefilter("always")
                        date_taken = get_date_taken(filepath)
                        
                        # Check if any warnings were raised
                        if w:
                            warning_files += 1
                            warning_msg = str(w[0].message) if w else "Unknown warning"
                            warning_files_list.append((filepath, warning_msg))
                            print(f"  ⚠ Warning on: {filename} - {warning_msg}")
                    
                    if date_taken:
                        # Check if date matches folder structure
                        match_result = dates_match_folder(date_taken, filepath)
                        
                        if match_result is False:
                            # Date exists but doesn't match folder
                            files_with_mismatched_date += 1
                            folder_year, folder_month = extract_date_from_path(filepath)
                            files_with_mismatched_date_list.append((filepath, date_taken, folder_year, folder_month))
                        
                        files_with_date += 1
                        files_with_date_list.append((filepath, date_taken, False))
                    else:
                        # Try to get date from folder structure
                        folder_year, folder_month = extract_date_from_path(filepath)
                        if folder_year and folder_month:
                            folder_date = f"{folder_year}:{folder_month}:01 00:00:00"
                            files_with_folder_date += 1
                            files_with_folder_date_list.append((filepath, folder_date, True))
                        else:
                            files_without_date += 1
                            files_without_date_list.append(filepath)
                except Exception as e:
                    error_files += 1
                    error_files_list.append((filepath, str(e)))
            else:
                non_image_files += 1
                skipped_files_list.append(filepath)
    
    return {
        'with_date': files_with_date,
        'with_folder_date': files_with_folder_date,
        'with_mismatched_date': files_with_mismatched_date,
        'without_date': files_without_date,
        'non_image': non_image_files,
        'video_files': video_files,
        'error_files': error_files,
        'warning_files': warning_files,
        'with_date_list': files_with_date_list,
        'with_folder_date_list': files_with_folder_date_list,
        'with_mismatched_date_list': files_with_mismatched_date_list,
        'without_date_list': files_without_date_list,
        'skipped_files_list': skipped_files_list,
        'video_files_list': video_files_list,
        'error_files_list': error_files_list,
        'warning_files_list': warning_files_list
    }

def move_files_with_date(files_with_date_list, destination_folder):
    """
    Move files with valid EXIF date taken to destination folder.
    If a file with the same name exists and has a different size,
    rename the source file by appending _dupN before the extension.
    Returns lists of moved and skipped files.
    """
    moved_files = []
    skipped_files = []

    # Create destination folder if it doesn't exist
    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)
        print(f"Created destination folder: {destination_folder}")

    print(f"\nMoving {len(files_with_date_list)} files to {destination_folder}...")

    for filepath, date_taken, from_folder in files_with_date_list:
        filename = os.path.basename(filepath)
        dest_path = os.path.join(destination_folder, filename)

        if os.path.exists(dest_path):
            src_size = os.path.getsize(filepath)
            dest_size = os.path.getsize(dest_path)
            if src_size == dest_size:
                skipped_files.append((filepath, dest_path, "File already exists (same size)"))
                print(f"  SKIP: {filename} (already exists, same size)")
                continue
            else:
                # Find a new name with _dupN
                name, ext = os.path.splitext(filename)
                n = 1
                while True:
                    new_filename = f"{name}_dup{n}{ext}"
                    new_dest_path = os.path.join(destination_folder, new_filename)
                    if not os.path.exists(new_dest_path):
                        break
                    n += 1
                try:
                    shutil.move(filepath, new_dest_path)
                    moved_files.append((filepath, new_dest_path))
                    print(f"  MOVED: {filename} as {new_filename} (size differs)")
                except Exception as e:
                    skipped_files.append((filepath, new_dest_path, str(e)))
                    print(f"  ERROR: {filename} - {e}")
        else:
            try:
                shutil.move(filepath, dest_path)
                moved_files.append((filepath, dest_path))
                print(f"  MOVED: {filename}")
            except Exception as e:
                skipped_files.append((filepath, dest_path, str(e)))
                print(f"  ERROR: {filename} - {e}")

    return moved_files, skipped_files

def main():
    # Get directory path from user
    default_dir = r"C:\Users\brian\OneDrive\Pictures\Camera Roll"
    directory = input(f"Enter the directory path to scan (default: {default_dir}): ").strip()
    
    # Use default if user just presses Enter
    if not directory:
        directory = default_dir
    
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
    
    # Append timestamp to output file name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name, ext = os.path.splitext(output_file)
    output_file = f"{name}_{timestamp}{ext}"
    
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
    output_lines.append(f"  - Mismatched with folder:  {results['with_mismatched_date']}")
    output_lines.append(f"Files with date from folder: {results['with_folder_date']}")
    output_lines.append(f"Files WITHOUT any date:      {results['without_date']}")
    output_lines.append(f"Video files (skipped):       {results['video_files']}")
    output_lines.append(f"Non-image files (skipped):   {results['non_image']}")
    output_lines.append(f"Files with errors:           {results['error_files']}")
    output_lines.append(f"Files with warnings:         {results['warning_files']}")
    output_lines.append(f"Total image files:           {results['with_date'] + results['with_folder_date'] + results['without_date']}")
    output_lines.append("="*60)
    
    # Display results on screen
    for line in output_lines:
        print(line)
    
    # Ask if user wants to see detailed lists
    show_details = input("\nInclude detailed file lists in output? (y/n): ").strip().lower()
    
    if show_details == 'y':
        if results['error_files_list']:
            output_lines.append("\n--- Files That Caused Errors ---")
            print("\n--- Files That Caused Errors ---")
            for filepath, error_msg in results['error_files_list']:
                line = f"  ❌ {filepath}"
                output_lines.append(line)
                print(line)
        
        if results['warning_files_list']:
            output_lines.append("\n--- Files That Caused Warnings ---")
            print("\n--- Files That Caused Warnings ---")
            for filepath, warning_msg in results['warning_files_list']:
                line = f"  ⚠ {filepath}"
                detail_line = f"     {warning_msg}"
                output_lines.append(line)
                output_lines.append(detail_line)
                print(line)
                print(detail_line)
        
        if results['with_mismatched_date_list']:
            output_lines.append("\n--- Files WHERE Date Does NOT Match Folder ---")
            print("\n--- Files WHERE Date Does NOT Match Folder ---")
            for filepath, date_taken, folder_year, folder_month in results['with_mismatched_date_list']:
                formatted_date = format_date_taken(date_taken, False)
                line = f"  ⚠ [{formatted_date}] in folder {folder_year}\\{folder_month}: {filepath}"
                output_lines.append(line)
                print(line)
        
        if results['with_date_list']:
            output_lines.append("\n--- Files WITH Date Taken (from EXIF) ---")
            print("\n--- Files WITH Date Taken (from EXIF) ---")
            for filepath, date_taken, from_folder in results['with_date_list']:
                formatted_date = format_date_taken(date_taken, from_folder)
                line = f"  ✓ [{formatted_date}] {filepath}"
                output_lines.append(line)
                print(line)
        
        if results['with_folder_date_list']:
            output_lines.append("\n--- Files WITH Date from Folder Structure ---")
            print("\n--- Files WITH Date from Folder Structure ---")
            for filepath, date_taken, from_folder in results['with_folder_date_list']:
                formatted_date = format_date_taken(date_taken, from_folder)
                line = f"  📁 [{formatted_date}] {filepath}"
                output_lines.append(line)
                print(line)
        
        if results['without_date_list']:
            output_lines.append("\n--- Files WITHOUT Any Date ---")
            print("\n--- Files WITHOUT Any Date ---")
            for f in results['without_date_list']:
                line = f"  ✗ {f}"
                output_lines.append(line)
                print(line)
        
        if results['video_files_list']:
            output_lines.append("\n--- Video Files (Skipped) ---")
            print("\n--- Video Files (Skipped) ---")
            for f in results['video_files_list']:
                line = f"  🎬 {f}"
                output_lines.append(line)
                print(line)
        
        if results['skipped_files_list']:
            output_lines.append("\n--- Non-Image Files (Skipped) ---")
            print("\n--- Non-Image Files (Skipped) ---")
            for f in results['skipped_files_list']:
                line = f"  ⊘ {f}"
                output_lines.append(line)
                print(line)
    
    # Write to file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(output_lines))
        print(f"\n✓ Results saved to: {output_file}")
    except Exception as e:
        print(f"\n✗ Error saving file: {e}")
    
    # Ask about moving files with valid date taken
    if results['with_date'] > 0:
        print(f"\n{'='*60}")
        print(f"Found {results['with_date']} files with valid 'Date Taken' in EXIF data.")
        
        # Save list of files to be moved FIRST
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        files_to_move_list = f"files_to_move_{timestamp}.txt"
        
        print(f"\nSaving list of files to: {files_to_move_list}")
        with open(files_to_move_list, 'w', encoding='utf-8') as f:
            f.write(f"Files with valid Date Taken to be moved to C:\\Users\\brian\\Pictures\\iCloud Photos\\Photos\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*60 + "\n\n")
            for filepath, date_taken, from_folder in results['with_date_list']:
                formatted_date = format_date_taken(date_taken, from_folder)
                f.write(f"[{formatted_date}] {filepath}\n")
        
        print(f"✓ File list saved. Please review: {files_to_move_list}")
        print("\nPress Enter after reviewing the file list to continue...")
        input()
        
        move_choice = input("Do you want to move these files to C:\\Users\\brian\\Pictures\\iCloud Photos\\Photos? (y/n): ").strip().lower()
        
        if move_choice == 'y':
            destination = r"C:\Users\brian\Pictures\iCloud Photos\Photos"
            
            # Perform the move
            moved_files, skipped_files = move_files_with_date(results['with_date_list'], destination)
            
            # Save results
            print(f"\nMove operation completed:")
            print(f"  Files moved: {len(moved_files)}")
            print(f"  Files skipped: {len(skipped_files)}")
            
            # Save skipped files list if any
            if skipped_files:
                skipped_files_list = f"files_skipped_{timestamp}.txt"
                print(f"\nSaving list of skipped files to: {skipped_files_list}")
                with open(skipped_files_list, 'w', encoding='utf-8') as f:
                    f.write(f"Files that could not be moved\n")
                    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("="*60 + "\n\n")
                    for source, dest, reason in skipped_files:
                        f.write(f"Source: {source}\n")
                        f.write(f"Destination: {dest}\n")
                        f.write(f"Reason: {reason}\n\n")
            
            # Save moved files list
            if moved_files:
                moved_files_list = f"files_moved_{timestamp}.txt"
                print(f"Saving list of moved files to: {moved_files_list}")
                with open(moved_files_list, 'w', encoding='utf-8') as f:
                    f.write(f"Files successfully moved to {destination}\n")
                    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("="*60 + "\n\n")
                    for source, dest in moved_files:
                        f.write(f"From: {source}\n")
                        f.write(f"To:   {dest}\n\n")

if __name__ == "__main__":
    main()