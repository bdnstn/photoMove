import os
import re
import time
from datetime import datetime, timezone, timedelta
import json
import subprocess
from pathlib import Path

SOURCE_DIR = r'C:\Users\brian\Pictures\CameraRollWorkingCopy'
DEST_DIR = r'C:\Users\brian\Pictures\iCloud Photos\Photos'
LOG_FILE = 'move_candidates.txt'
ERROR_LOG_FILE = 'move_errors.txt'

def get_folder_date(filepath):
    """Extract year and month from folder structure, return first day of month"""
    try:
        parts = Path(filepath).parts
        for i in range(len(parts)-1):
            # Look for year folder (4 digits)
            if re.match(r'^\d{4}$', parts[i]):
                year = int(parts[i])
                # Check if next part is month (1-12)
                if i+1 < len(parts) and re.match(r'^\d{1,2}$', parts[i+1]):
                    month = int(parts[i+1])
                    if 1 <= month <= 12:
                        return datetime(year, month, 1).replace(tzinfo=timezone.utc)
    except Exception:
        pass
    return None

def get_exif_date_taken(filepath):
    """Get DateTimeOriginal from EXIF data"""
    try:
        result = subprocess.run(
            ['exiftool', '-DateTimeOriginal', '-d', '%Y:%m:%d %H:%M:%S', filepath],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if 'Date/Time Original' in line:
                    date_str = line.split(': ', 1)[1].strip()
                    return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S').replace(tzinfo=timezone.utc)
    except Exception:
        pass
    return None

def set_exif_date_taken(filepath, date):
    """Set DateTimeOriginal in file's EXIF data"""
    date_str = date.strftime('%Y:%m:%d %H:%M:%S')
    result = subprocess.run(
        ['exiftool', f'-DateTimeOriginal={date_str}', '-overwrite_original', filepath],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    return result.returncode == 0

def count_exif_tags(filepath):
    """Count number of EXIF tags in file"""
    try:
        result = subprocess.run(
            ['exiftool', '-j', filepath],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode == 0:
            metadata = json.loads(result.stdout)[0]
            return len(metadata) - 1  # Subtract 1 for SourceFile
    except Exception:
        pass
    return 0

def main():
    move_candidates = []
    existing_files = []

    print(f"Scanning source directory: {SOURCE_DIR}")
    
    # Walk through source directory
    for root, _, files in os.walk(SOURCE_DIR):
        for filename in files:
            src_path = os.path.join(root, filename)
            dest_path = os.path.join(DEST_DIR, filename)
            
            # Check if file already exists at destination
            if os.path.exists(dest_path):
                src_size = os.path.getsize(src_path)
                dest_size = os.path.getsize(dest_path)
                src_tags = count_exif_tags(src_path)
                dest_tags = count_exif_tags(dest_path)
                existing_files.append({
                    'filename': filename,
                    'src_path': src_path,
                    'src_size': src_size,
                    'src_tags': src_tags,
                    'dest_path': dest_path,
                    'dest_size': dest_size,
                    'dest_tags': dest_tags
                })
                continue

            # Check for existing date taken
            date_taken = get_exif_date_taken(src_path)
            if not date_taken:
                # Try to get date from folder structure
                date_taken = get_folder_date(src_path)
                if date_taken:
                    move_candidates.append({
                        'src_path': src_path,
                        'dest_path': dest_path,
                        'date_taken': date_taken,
                        'needs_date': True
                    })
            else:
                move_candidates.append({
                    'src_path': src_path,
                    'dest_path': dest_path,
                    'date_taken': date_taken,
                    'needs_date': False
                })

    # Write move candidates log
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(f"Move candidates - generated {datetime.now()}\n")
        f.write(f"Source: {SOURCE_DIR}\n")
        f.write(f"Destination: {DEST_DIR}\n")
        f.write(f"Total files to move: {len(move_candidates)}\n")
        f.write("="*60 + "\n\n")
        for entry in move_candidates:
            f.write(f"Source: {entry['src_path']}\n")
            f.write(f"Destination: {entry['dest_path']}\n")
            f.write(f"Date Taken: {entry['date_taken']}\n")
            if entry['needs_date']:
                f.write("Note: Date will be written from folder structure\n")
            f.write("-"*40 + "\n\n")

    # Write error log for existing files
    if existing_files:
        with open(ERROR_LOG_FILE, 'w', encoding='utf-8') as f:
            f.write(f"Files already existing at destination - {datetime.now()}\n")
            f.write("="*60 + "\n\n")
            for entry in existing_files:
                f.write(f"Filename: {entry['filename']}\n")
                f.write(f"Source Path: {entry['src_path']}\n")
                f.write(f"Source Size: {entry['src_size']:,} bytes\n")
                f.write(f"Source Tags: {entry['src_tags']}\n")
                f.write(f"Destination Path: {entry['dest_path']}\n")
                f.write(f"Destination Size: {entry['dest_size']:,} bytes\n")
                f.write(f"Destination Tags: {entry['dest_tags']}\n")
                f.write("-"*40 + "\n\n")

        # Add prompt to delete matching source files
        exact_matches = [entry for entry in existing_files 
                        if entry['src_size'] == entry['dest_size'] 
                        and entry['src_tags'] == entry['dest_tags']]
        
        if exact_matches:
            print(f"\nFound {len(exact_matches)} files that match exactly (same size and tag count)")
            delete = input("Do you want to delete these source files? (y/n): ").strip().lower()
            if delete == 'y':
                for entry in exact_matches:
                    try:
                        os.remove(entry['src_path'])
                        print(f"Deleted: {entry['filename']}")
                    except Exception as e:
                        print(f"Failed to delete {entry['filename']}: {e}")
            else:
                print("No files were deleted.")

    print(f"\nFound {len(move_candidates)} files to move")
    print(f"Found {len(existing_files)} files that already exist at destination")
    print(f"\nMove candidates written to: {LOG_FILE}")
    if existing_files:
        print(f"Existing files written to: {ERROR_LOG_FILE}")

    if move_candidates:
        proceed = input("\nDo you want to proceed with moving files? (y/n): ").strip().lower()
        if proceed == 'y':
            for entry in move_candidates:
                try:
                    # Debug check - this shouldn't happen
                    if os.path.exists(entry['dest_path']):
                        print(f"WARNING: {entry['dest_path']} exists but wasn't caught in initial scan!")
                        continue

                    if entry['needs_date']:
                        if set_exif_date_taken(entry['src_path'], entry['date_taken']):
                            print(f"Set date taken for: {os.path.basename(entry['src_path'])}")
                        else:
                            print(f"Failed to set date taken for: {os.path.basename(entry['src_path'])}")
                    
                    os.rename(entry['src_path'], entry['dest_path'])
                    print(f"Moved: {os.path.basename(entry['src_path'])}")
                except Exception as e:
                    print(f"Error moving {os.path.basename(entry['src_path'])}: {e}")
                    print(f"Source exists: {os.path.exists(entry['src_path'])}")
                    print(f"Destination exists: {os.path.exists(entry['dest_path'])}")
        else:
            print("Operation cancelled")

if __name__ == "__main__":
    main()