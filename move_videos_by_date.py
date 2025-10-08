import os
import subprocess
from datetime import datetime
import shutil

START_DIR = r'C:\Users\brian\Pictures\CameraRollWorkingCopy'
DEST_DIR = r'C:\Users\brian\Pictures\iCloud Photos\Photos'
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.3gp', '.m4v', '.mpg', '.mpeg'}

def get_media_created(filepath):
    result = subprocess.run(
        ['exiftool', '-MediaCreateDate', '-d', '%Y:%m:%d %H:%M:%S', filepath],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if 'Media Create Date' in line:
            return line.split(': ', 1)[1].strip()
    return None

def get_date_taken(filepath):
    result = subprocess.run(
        ['exiftool', '-DateTimeOriginal', '-d', '%Y:%m:%d %H:%M:%S', filepath],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if 'Date/Time Original' in line:
            return line.split(': ', 1)[1].strip()
    return None

def scan_videos_with_dates(start_dir):
    videos_with_media_date = []
    videos_missing_date_taken = []
    for root, _, files in os.walk(start_dir):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in VIDEO_EXTENSIONS:
                filepath = os.path.join(root, file)
                media_date = get_media_created(filepath)
                if media_date:
                    date_taken = get_date_taken(filepath)
                    videos_with_media_date.append((filepath, media_date, date_taken))
                    if not date_taken:
                        videos_missing_date_taken.append((filepath, media_date))
    return videos_with_media_date, videos_missing_date_taken

def set_date_taken(filepath, media_date):
    # Convert media_date from 'DD/MM/YYYY HH:MM AM/PM' to 'YYYY:MM:DD HH:MM:SS'
    try:
        # Try parsing with AM/PM
        dt = datetime.strptime(media_date, "%d/%m/%Y %I:%M %p")
    except ValueError:
        try:
            # Try parsing without AM/PM
            dt = datetime.strptime(media_date, "%d/%m/%Y %H:%M")
        except ValueError:
            # Try parsing ExifTool's default output
            try:
                dt = datetime.strptime(media_date, "%Y:%m:%d %H:%M:%S")
            except ValueError:
                print(f"Unrecognized date format: {media_date}")
                return False
    formatted_date = dt.strftime("%Y:%m:%d %H:%M:%S")
    result = subprocess.run(
        ['exiftool', f'-DateTimeOriginal={formatted_date}', '-overwrite_original', filepath],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    return result.returncode == 0

def main():
    print(f"Scanning for video files with 'Media Create Date' in {START_DIR} ...")
    videos, missing_date_taken = scan_videos_with_dates(START_DIR)
    print(f"Found {len(videos)} video files with 'Media Create Date'.")
    print(f"{len(missing_date_taken)} files have 'Media Create Date' but no 'Date Taken'.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    list_file = f"videos_with_date_{timestamp}.txt"
    missing_file = f"videos_missing_date_taken_{timestamp}.txt"

    # Write all videos with media date
    with open(list_file, 'w', encoding='utf-8') as f:
        f.write(f"Video files with Media Create Date\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*60 + "\n\n")
        for filepath, media_date, date_taken in videos:
            f.write(f"[Media Created: {media_date}] [Date Taken: {date_taken}] {filepath}\n")
    print(f"List saved to {list_file}.")

    # Write log of files missing Date Taken
    if missing_date_taken:
        with open(missing_file, 'w', encoding='utf-8') as f:
            f.write(f"Video files with Media Create Date but missing Date Taken\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*60 + "\n\n")
            for filepath, media_date in missing_date_taken:
                f.write(f"[Media Created: {media_date}] {filepath}\n")
        print(f"Files missing 'Date Taken' logged to {missing_file}.")
        fix = input("Set 'Date Taken' to 'Media Created' for these files? (y/n): ").strip().lower()
        if fix == 'y':
            for filepath, media_date in missing_date_taken:
                success = set_date_taken(filepath, media_date)
                if success:
                    print(f"✓ Set Date Taken for {os.path.basename(filepath)}")
                else:
                    print(f"✗ Failed to set Date Taken for {os.path.basename(filepath)}")
        else:
            print("No changes made to 'Date Taken'.")

    move = input(f"Do you want to move these files to {DEST_DIR}? (y/n): ").strip().lower()
    if move == 'y':
        if not os.path.exists(DEST_DIR):
            os.makedirs(DEST_DIR)
        for filepath, media_date, date_taken in videos:
            filename = os.path.basename(filepath)
            dest_path = os.path.join(DEST_DIR, filename)
            if os.path.exists(dest_path):
                print(f"SKIP: {filename} (already exists at destination)")
                continue
            try:
                shutil.move(filepath, dest_path)
                print(f"MOVED: {filename}")
            except Exception as e:
                print(f"ERROR moving {filename}: {e}")
    else:
        print("No files were moved.")

if __name__ == "__main__":
    main()