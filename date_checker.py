import os
from PIL import Image
from PIL.ExifTags import TAGS
from pathlib import Path

def get_date_taken(filepath):
    """
    Extract 'Date Taken' from image EXIF data.
    Returns the date if found, None otherwise.
    """
    try:
        image = Image.open(filepath)
        exif_data = image._getexif()
        
        if exif_data is not None:
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == 'DateTimeOriginal' or tag == 'DateTime':
                    return value
        return None
    except Exception:
        return None

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
                    files_with_date_list.append(filepath)
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
    
    # Scan the directory
    results = scan_directory(directory)
    
    # Display results
    print("\n" + "="*60)
    print("SCAN RESULTS")
    print("="*60)
    print(f"Files WITH 'Date Taken':    {results['with_date']}")
    print(f"Files WITHOUT 'Date Taken':  {results['without_date']}")
    print(f"Non-image files (skipped):   {results['non_image']}")
    print(f"Total image files:           {results['with_date'] + results['without_date']}")
    print("="*60)
    
    # Ask if user wants to see detailed lists
    show_details = input("\nShow detailed file lists? (y/n): ").strip().lower()
    
    if show_details == 'y':
        if results['with_date_list']:
            print("\n--- Files WITH Date Taken ---")
            for f in results['with_date_list']:
                print(f"  ✓ {f}")
        
        if results['without_date_list']:
            print("\n--- Files WITHOUT Date Taken ---")
            for f in results['without_date_list']:
                print(f"  ✗ {f}")

if __name__ == "__main__":
    main()