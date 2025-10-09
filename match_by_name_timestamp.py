import os
import re
import time
from datetime import datetime, timezone, timedelta
import json
import subprocess

SOURCE_DIR = r'C:\Users\brian\Pictures\CameraRollWorkingCopy'
DEST_DIR = r'C:\Users\brian\Pictures\iCloud Photos\Photos'
LOG_FILE = 'mov_matches_log.txt'

# Regex for YYYYMMDD_HHMMSSmmm_iOS.<ext>
FILENAME_PATTERN = re.compile(r'^(\d{8}_\d{9})_iOS\.(\w+)$', re.IGNORECASE)

def find_files_with_pattern(directory):
    matches = {}
    for root, _, files in os.walk(directory):
        for file in files:
            match = FILENAME_PATTERN.match(file)
            if match:
                timestamp = match.group(1)
                ext = match.group(2).lower()
                full_path = os.path.join(root, file)
                matches[(timestamp, ext)] = full_path
    return matches

def parse_filename_timestamp(ts_str):
    # Parse 'YYYYMMDD_HHMMSSmmm' to datetime (assume UTC)
    return datetime.strptime(ts_str, "%Y%m%d_%H%M%S%f").replace(tzinfo=timezone.utc)

def get_file_created_time(filepath):
    # Get local created time and convert to UTC
    local_dt = datetime.fromtimestamp(os.path.getctime(filepath))
    offset_sec = -time.altzone if time.daylight else -time.timezone
    offset = timedelta(seconds=offset_sec)
    utc_dt = local_dt - offset
    return utc_dt.replace(tzinfo=timezone.utc)

def count_exif_tags(filepath):
    # Use exiftool to count tags
    try:
        result = subprocess.run(
            ['exiftool', filepath],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode != 0:
            return 0
        # Each line is a tag (format: Tag Name : Value)
        tag_lines = [line for line in result.stdout.splitlines() if ':' in line]
        return len(tag_lines)
    except Exception:
        return 0

def count_exif_tags_batch(filepaths):
    # Returns a dict: {filepath: tag_count}
    if not filepaths:
        return {}
    result = subprocess.run(
        ['exiftool', '-j'] + filepaths,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    tag_counts = {}
    try:
        metadata_list = json.loads(result.stdout)
        for metadata in metadata_list:
            # ExifTool outputs 'SourceFile' as the full path
            path = metadata.get('SourceFile')
            if path:
                # Exclude 'SourceFile' key itself from tag count
                tag_counts[path] = len(metadata) - 1
    except Exception as e:
        print(f"Error parsing ExifTool output: {e}")
    return tag_counts

def main():

    print("Scanning source directory for files with timestamp pattern ending _iOS...")
    source_files = find_files_with_pattern(SOURCE_DIR)
    print(f"Found {len(source_files)} matching files in source.")

    print("Scanning destination directory for all files...")

    # Build index for destination files and count total files
    dest_index = {}
    total_dest_files = 0
    for root, _, files in os.walk(DEST_DIR):
        total_dest_files += len(files)
        for file in files:
            ext = os.path.splitext(file)[1][1:].lower()
            full_path = os.path.join(root, file)
            try:
                dest_dt = get_file_created_time(full_path).replace(microsecond=0)
                dest_index[(dest_dt, ext)] = full_path
            except Exception as e:
                print(f"Error getting created time for {full_path}: {e}")
                continue

    print(f"Found {total_dest_files} total files in destination")
    print(f"Indexed {len(dest_index)} files in destination with valid timestamps")

    matched = []
    unmatched = []
    for (timestamp, src_ext), src_path in source_files.items():
        src_dt = parse_filename_timestamp(timestamp).replace(microsecond=0)
        key = (src_dt, src_ext)
        if key in dest_index:
            # Use all matching files for logging/matching
            for dest_path in dest_index[key]:
                matched.append((timestamp, src_path, dest_path))
        else:
            unmatched.append((timestamp, src_path, src_ext))

    print(f"Found {len(matched)} matching files in both directories.")
    print(f"Found {len(unmatched)} unmatched files in source.")

    # Ask user if they want to count EXIF tags
    count_tags = input("Do you want to count EXIF tags for matched files? (y/n): ").strip().lower() == 'y'
    src_tag_counts = {}
    dest_tag_counts = {}
    if count_tags and matched:
        src_paths = [src_path for _, src_path, _ in matched]
        dest_paths = [dest_path for _, _, dest_path in matched]
        src_tag_counts = count_exif_tags_batch(src_paths)
        dest_tag_counts = count_exif_tags_batch(dest_paths)

    # Write log of matched files only, including tag counts if requested
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(f"Matching files by filename timestamp (UTC), file created time (UTC), and filetype\n")
        f.write(f"Source: {SOURCE_DIR}\nDestination: {DEST_DIR}\n")
        f.write(f"Total matches: {len(matched)}\n")
        f.write("="*60 + "\n\n")
        f.write("Matched files:\n")
        for timestamp, src_path, dest_path in matched:
            dest_dt = get_file_created_time(dest_path)
            f.write(f"Timestamp: {timestamp}\nSource: {src_path}\n")
            if count_tags:
                src_tags = src_tag_counts.get(src_path, 0)
                dest_tags = dest_tag_counts.get(dest_path, 0)
                f.write(f"Source Tag Count: {src_tags}\n")
                f.write(f"Destination: {dest_path}\n")
                f.write(f"Destination Tag Count: {dest_tags}\n")
            else:
                f.write(f"Destination: {dest_path}\n")
            f.write(f"Destination Created Time (UTC): {dest_dt}\n\n")
        f.write("Unmatched files:\n")
        for timestamp, src_path, src_ext in unmatched:
            f.write(f"Timestamp: {timestamp}\nSource: {src_path}\nFiletype: {src_ext}\n\n")

    print(f"Log written to {LOG_FILE}")

    # Prompt for optional deletion
    if matched:
        delete = input("Do you want to delete the matched source files? (y/n): ").strip().lower()
        if delete == 'y':
            for _, src_path, _ in matched:
                try:
                    os.remove(src_path)
                    print(f"Deleted: {src_path}")
                except Exception as e:
                    print(f"Failed to delete {src_path}: {e}")
        else:
            print("No files were deleted.")

    # Prompt for optional move of unmatched files
    if unmatched:
        move = input("Do you want to move unmatched source files to the destination? (y/n): ").strip().lower()
        if move == 'y':
            skipped_log = []
            skipped_same_size = []
            for _, src_path, src_ext in unmatched:
                filename = os.path.basename(src_path)
                dest_path = os.path.join(DEST_DIR, filename)
                if os.path.exists(dest_path):
                    # Get file sizes
                    src_size = os.path.getsize(src_path)
                    dest_size = os.path.getsize(dest_path)
                    # Get file dates
                    src_date = datetime.fromtimestamp(os.path.getctime(src_path))
                    dest_date = datetime.fromtimestamp(os.path.getctime(dest_path))
                    
                    if src_size == dest_size:
                        skipped_same_size.append((src_path, src_size))
                        print(f"SKIP: {filename} (exists with same size)")
                    else:
                        skipped_log.append({
                            'filename': filename,
                            'src_path': src_path,
                            'src_size': src_size,
                            'src_date': src_date,
                            'dest_path': dest_path,
                            'dest_size': dest_size,
                            'dest_date': dest_date
                        })
                        print(f"SKIP: {filename} (exists with different size)")
                    continue
                try:
                    os.rename(src_path, dest_path)
                    print(f"MOVED: {filename}")
                except Exception as e:
                    print(f"Failed to move {filename}: {e}")
            
            # Prompt to delete files that exist with same size
            if skipped_same_size:
                print(f"\nFound {len(skipped_same_size)} files that exist at destination with same size")
                delete = input("Do you want to delete these source files? (y/n): ").strip().lower()
                if delete == 'y':
                    for src_path, size in skipped_same_size:
                        try:
                            os.remove(src_path)
                            print(f"Deleted: {os.path.basename(src_path)} ({size:,} bytes)")
                        except Exception as e:
                            print(f"Failed to delete {os.path.basename(src_path)}: {e}")
            
            # Write skipped files log if any files were skipped with different sizes
            if skipped_log:
                skip_log_file = f'skipped_moves_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
                with open(skip_log_file, 'w', encoding='utf-8') as f:
                    f.write("Files skipped during move (filename exists with different size)\n")
                    f.write("="*60 + "\n\n")
                    for entry in skipped_log:
                        f.write(f"Filename: {entry['filename']}\n")
                        f.write(f"Source Path: {entry['src_path']}\n")
                        f.write(f"Source Size: {entry['src_size']:,} bytes\n")
                        f.write(f"Source Date: {entry['src_date']}\n")
                        f.write(f"Destination Path: {entry['dest_path']}\n")
                        f.write(f"Destination Size: {entry['dest_size']:,} bytes\n")
                        f.write(f"Destination Date: {entry['dest_date']}\n")
                        f.write("-"*40 + "\n\n")
                print(f"Skipped files log written to {skip_log_file}")
        else:
            print("No files were moved.")

if __name__ == "__main__":
    main()