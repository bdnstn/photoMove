import os
import re
import time
from datetime import datetime, timezone, timedelta

SOURCE_DIR = r'C:\Users\brian\Pictures\CameraRollWorkingCopy'
DEST_DIR = r'C:\Users\brian\Pictures\iCloud Photos\Photos'
LOG_FILE = 'mov_matches_log.txt'

FILENAME_PATTERN = re.compile(r'^(\d{8}_\d{9})_iOS\.mov$', re.IGNORECASE)

def find_mov_files_with_pattern(directory):
    matches = {}
    for root, _, files in os.walk(directory):
        for file in files:
            match = FILENAME_PATTERN.match(file)
            if match:
                timestamp = match.group(1)
                full_path = os.path.join(root, file)
                matches[timestamp] = full_path
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

def main():

    print("Scanning source directory for .mov files with timestamp pattern ending _iOS...")
    source_files = find_mov_files_with_pattern(SOURCE_DIR)
    print(f"Found {len(source_files)} matching .mov files in source.")

    print("Scanning destination directory for .mov files...")
    dest_files = []
    for root, _, files in os.walk(DEST_DIR):
        for file in files:
            if file.lower().endswith('.mov'):
                full_path = os.path.join(root, file)
                dest_files.append(full_path)

    print(f"Found {len(dest_files)} .mov files in destination.")

    matched = []
    for timestamp, src_path in source_files.items():
        src_dt = parse_filename_timestamp(timestamp).replace(microsecond=0)
        for dest_path in dest_files:
            dest_dt = get_file_created_time(dest_path).replace(microsecond=0)
            if src_dt == dest_dt:
                matched.append((timestamp, src_path, dest_path))

    print(f"Found {len(matched)} matching files in both directories.")

    # Write log of matched files only
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(f"Matching .mov files by filename timestamp (UTC) and file created time (UTC)\n")
        f.write(f"Source: {SOURCE_DIR}\nDestination: {DEST_DIR}\n")
        f.write(f"Total matches: {len(matched)}\n")
        f.write("="*60 + "\n\n")
        f.write("Matched files:\n")
        for timestamp, src_path, dest_path in matched:
            dest_dt = get_file_created_time(dest_path)
            f.write(f"Timestamp: {timestamp}\nSource: {src_path}\nDestination: {dest_path}\nDestination Created Time (UTC): {dest_dt}\n\n")

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