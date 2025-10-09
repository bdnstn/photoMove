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

    # Build index for destination files
    dest_index = {}
    for root, _, files in os.walk(DEST_DIR):
        for file in files:
            ext = os.path.splitext(file)[1][1:].lower()
            full_path = os.path.join(root, file)
            dest_dt = get_file_created_time(full_path).replace(microsecond=0)
            dest_index[(dest_dt, ext)] = full_path

    print(f"Indexed {len(dest_index)} files in destination.")

    matched = []
    for (timestamp, src_ext), src_path in source_files.items():
        src_dt = parse_filename_timestamp(timestamp).replace(microsecond=0)
        key = (src_dt, src_ext)
        if key in dest_index:
            matched.append((timestamp, src_path, dest_index[key]))

    print(f"Found {len(matched)} matching files in both directories.")

    # Before writing the log
    src_paths = [src_path for _, src_path, _ in matched]
    dest_paths = [dest_path for _, _, dest_path in matched]
    src_tag_counts = count_exif_tags_batch(src_paths)
    dest_tag_counts = count_exif_tags_batch(dest_paths)

    # Write log of matched files only, including tag counts
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(f"Matching files by filename timestamp (UTC), file created time (UTC), and filetype\n")
        f.write(f"Source: {SOURCE_DIR}\nDestination: {DEST_DIR}\n")
        f.write(f"Total matches: {len(matched)}\n")
        f.write("="*60 + "\n\n")
        f.write("Matched files:\n")
        for timestamp, src_path, dest_path in matched:
            dest_dt = get_file_created_time(dest_path)
            src_tags = src_tag_counts.get(src_path, 0)
            dest_tags = dest_tag_counts.get(dest_path, 0)
            f.write(
                f"Timestamp: {timestamp}\n"
                f"Source: {src_path}\n"
                f"Source Tag Count: {src_tags}\n"
                f"Destination: {dest_path}\n"
                f"Destination Tag Count: {dest_tags}\n"
                f"Destination Created Time (UTC): {dest_dt}\n\n"
            )

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

if __name__ == "__main__":
    main()