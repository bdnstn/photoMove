import os
from PIL import Image
from PIL.ExifTags import TAGS
from pathlib import Path
import time
from datetime import datetime
import re
import shutil
import warnings
import subprocess
import json
import tempfile
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_SUPPORT = True
except ImportError:
    HEIF_SUPPORT = False

# Threaded fallback for faster in-process EXIF extraction
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback

# Increase the decompression bomb limit or catch the warning
Image.MAX_IMAGE_PIXELS = None  # Remove limit entirely (or set to a higher value like 200000000)

# Reverse mapping for EXIF tag names -> tag ids
TAG_BY_NAME = {v: k for k, v in TAGS.items()}

def get_date_taken_pillow(filepath):
    """
    Fast in-process EXIF extraction using Pillow. Returns DateTimeOriginal or DateTime string
    in the format 'YYYY:MM:DD HH:MM:SS' when available, otherwise None.
    """
    try:
        with Image.open(filepath) as img:
            exif = img.getexif()
            if not exif:
                return None
            # Try DateTimeOriginal first, then DateTime
            for name in ('DateTimeOriginal', 'DateTime'):
                tag = TAG_BY_NAME.get(name)
                if tag and tag in exif:
                    val = exif.get(tag)
                    # Some EXIF values may be bytes
                    if isinstance(val, bytes):
                        try:
                            val = val.decode('utf-8', errors='ignore')
                        except Exception:
                            val = str(val)
                    return val
    except Exception:
        return None


def build_exif_mapping_pillow(filepaths, max_workers=None):
    """Build a mapping of absolute_path -> date_string using threads and Pillow."""
    mapping = {}
    if not filepaths:
        return mapping
    if max_workers is None:
        max_workers = min(32, (os.cpu_count() or 1) * 5)
    with ThreadPoolExecutor(max_workers=max_workers) as exe:
        futures = {exe.submit(get_date_taken_pillow, p): p for p in filepaths}
        for fut in as_completed(futures):
            p = futures[fut]
            try:
                res = fut.result()
            except Exception:
                res = None
            mapping[os.path.abspath(p)] = res
    return mapping

def get_date_taken(filepath):
    """
    Extract 'Date Taken' from image metadata using ExifTool.
    Returns the date if found, None otherwise.
    Only uses DateTimeOriginal.
    Raises exception with filepath if there's an error.
    """
    try:
        # Call ExifTool and get DateTimeOriginal only
        result = subprocess.run(
            ['exiftool', '-DateTimeOriginal', '-d', '%Y:%m:%d %H:%M:%S', filepath],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode != 0:
            raise Exception(result.stderr.strip())
        for line in result.stdout.splitlines():
            if 'Date/Time Original' in line:
                return line.split(': ', 1)[1].strip()
        return None
    except Exception as e:
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


def extract_date_from_filename(filepath):
    """
    Try to extract a date from the filename. Recognizes patterns like YYYYMMDD, YYYY-MM-DD, YYYY_MM_DD, YYYY.MM.DD.
    Returns a string formatted as 'YYYY:MM:DD 00:00:00' if found, otherwise None.
    """
    try:
        name = os.path.basename(filepath)
        # Common patterns: 20201231, 2020-12-31, 2020_12_31, 2020.12.31
        m = re.search(r'(19\d{2}|20\d{2})[\-_\.]?(0[1-9]|1[0-2])[\-_\.]?(0[1-9]|[12][0-9]|3[01])', name)
        if m:
            year, month, day = m.group(1), m.group(2), m.group(3)
            return f"{year}:{month}:{day} 00:00:00"
        # Also try compact YYYYMMDD
        m2 = re.search(r'(19\d{2}|20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])', name)
        if m2:
            year, month, day = m2.group(1), m2.group(2), m2.group(3)
            return f"{year}:{month}:{day} 00:00:00"
    except Exception:
        pass
    return None


def set_date_taken_exif(filepath, date_str, overwrite=False):
    """
    Set DateTimeOriginal EXIF tag using exiftool. Returns (True, output) on success, (False, err) on failure.
    If overwrite is False, exiftool will create backup files (default behavior). If overwrite is True, -overwrite_original is used.
    """
    try:
        if overwrite:
            cmd = ['exiftool', '-overwrite_original', f'-DateTimeOriginal={date_str}', filepath]
        else:
            cmd = ['exiftool', f'-DateTimeOriginal={date_str}', filepath]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            return False, result.stderr.strip()
        return True, result.stdout.strip()
    except Exception as e:
        return False, str(e) 

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

def _run_exiftool_batch(filepaths):
    """Run exiftool once on a list of file paths and return a dict mapping
    filepath -> DateTimeOriginal string (or None). Uses a temporary file to
    avoid command-line length limits. Returns None on failure."""
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False) as tf:
            for p in filepaths:
                tf.write(p + os.linesep)
            tf_name = tf.name
        cmd = ['exiftool', '-DateTimeOriginal', '-d', '%Y:%m:%d %H:%M:%S', '-j', '-@', tf_name]
        t0 = time.time()
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        duration = time.time() - t0
        # Clean up tempfile
        try:
            os.remove(tf_name)
        except Exception:
            pass
        if result.returncode != 0:
            # exiftool failed; log stderr for diagnosis and let caller handle fallback
            stderr_text = result.stderr.strip()
            print("⚠ exiftool batch run failed with exit code", result.returncode)
            if stderr_text:
                print("   exiftool stderr:")
                for line in stderr_text.splitlines():
                    print("     "+line)
                # Save a debug file with stderr to help investigation
                try:
                    dbg_name = f"exiftool_batch_error_{int(time.time())}.txt"
                    with open(dbg_name, 'w', encoding='utf-8') as dbgf:
                        dbgf.write('Command: ' + ' '.join(cmd) + os.linesep)
                        dbgf.write('Exit code: ' + str(result.returncode) + os.linesep)
                        dbgf.write('stderr:' + os.linesep + stderr_text + os.linesep)
                    print(f"   Debug info saved to: {dbg_name}")
                except Exception:
                    pass
            return None
        data = json.loads(result.stdout)
        mapping = {}
        found = 0
        for entry in data:
            path = entry.get('SourceFile')
            date = entry.get('DateTimeOriginal') or None
            if date:
                found += 1
            mapping[os.path.abspath(path)] = date
        print(f"✓ exiftool batch succeeded: found {found} dates in {duration:.2f}s")
        return mapping
    except Exception as e:
        print("⚠ Exception running exiftool batch:", str(e))
        return None


def exiftool_available():
    """Return True if the 'exiftool' executable is available on PATH."""
    try:
        result = subprocess.run(['exiftool', '-ver'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False
    except Exception:
        return False


def get_exiftool_version():
    """Return exiftool version string if available, otherwise None."""
    try:
        result = subprocess.run(['exiftool', '-ver'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        return None
    return None


def ffprobe_available():
    """Return True if 'ffprobe' is available on PATH."""
    try:
        result = subprocess.run(['ffprobe', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False
    except Exception:
        return False


def get_video_date_ffprobe(filepath):
    """
    Use ffprobe to extract creation_time from video file. Returns a string in
    'YYYY:MM:DD HH:MM:SS' format or None.
    """
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_entries', 'format_tags=creation_time,stream_tags=creation_time', '-i', filepath]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        # Check format tags
        creation = None
        fmt = data.get('format', {})
        tags = fmt.get('tags', {}) if isinstance(fmt, dict) else {}
        if 'creation_time' in tags:
            creation = tags.get('creation_time')
        # Check streams
        if not creation and 'streams' in data:
            for s in data['streams']:
                stags = s.get('tags', {})
                if stags and 'creation_time' in stags:
                    creation = stags.get('creation_time')
                    break
        if not creation:
            return None
        # Normalize ISO format to EXIF style
        # Examples: 2020-01-02T12:34:56.000000Z or 2020-01-02 12:34:56
        creation = creation.replace('Z', '')
        creation = creation.replace('T', ' ')
        # Trim fractional seconds
        creation = re.sub(r"\.\d+", '', creation)
        try:
            dt = datetime.fromisoformat(creation.strip())
            return dt.strftime('%Y:%m:%d %H:%M:%S')
        except Exception:
            # Fallback: try to parse common formats
            m = re.search(r'(\d{4})-(\d{2})-(\d{2}).*(\d{2}):(\d{2}):(\d{2})', creation)
            if m:
                return f"{m.group(1)}:{m.group(2)}:{m.group(3)} {m.group(4)}:{m.group(5)}:{m.group(6)}"
    except Exception:
        return None
    return None


def build_video_mapping_ffprobe(filepaths, max_workers=None):
    """Threaded ffprobe mapping for videos: absolute_path -> date string or None."""
    mapping = {}
    if not filepaths:
        return mapping
    if max_workers is None:
        max_workers = min(16, (os.cpu_count() or 1) * 4)
    with ThreadPoolExecutor(max_workers=max_workers) as exe:
        futures = {exe.submit(get_video_date_ffprobe, p): p for p in filepaths}
        for fut in as_completed(futures):
            p = futures[fut]
            try:
                res = fut.result()
            except Exception:
                res = None
            mapping[os.path.abspath(p)] = res
    return mapping


def scan_directory(directory_path):
    """
    Walk through directory structure and count files with/without date taken.
    This implementation batches EXIF extraction for all image files using
    exiftool to improve performance dramatically. If exiftool batch fails,
    it falls back to per-file extraction.
    """
    # Supported image extensions
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.heic', '.heif'}
    
    # Video extensions to skip
    video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.wmv', '.flv', '.webm', '.3gp', '.mpg', '.mpeg'}
    
    files_with_date = 0
    files_without_date = 0
    files_with_folder_date = 0
    files_with_filename_date = 0
    files_with_mismatched_date = 0
    non_image_files = 0
    video_files = 0
    error_files = 0
    warning_files = 0
    files_with_date_list = []
    files_without_date_list = []
    files_with_folder_date_list = []
    files_with_filename_date_list = []
    files_with_mismatched_date_list = []
    skipped_files_list = []
    video_files_list = []
    error_files_list = []
    warning_files_list = []

    # Stage 1: walk and classify files (fast)
    image_files = []
    media_files = []  # images + videos
    processed_files = 0
    video_files = 0
    video_files_list = []

    print(f"Scanning directory: {directory_path}\n")
    if not HEIF_SUPPORT:
        print("⚠ Warning: HEIC/HEIF support not available. Install pillow-heif for better results.")
        print("   Run: py -m pip install pillow-heif\n")

    scan_start_time = time.time()
    spinner_chars = ['|', '/', '-', '=']
    spinner_index = 0
    last_print_time = 0.0
    update_interval = 0.2  # seconds, throttle spinner updates
    prev_print_len = 0

    for root, dirs, files in os.walk(directory_path):
        for filename in files:
            processed_files += 1
            now = time.time()
            if now - last_print_time >= update_interval:
                elapsed = now - scan_start_time
                m, s = divmod(int(elapsed), 60)
                h, m = divmod(m, 60)
                elapsed_str = f"{h:d}:{m:02d}:{s:02d}" if h > 0 else f"{m:d}:{s:02d}"
                spinner_char = spinner_chars[spinner_index % len(spinner_chars)]
                spinner_index += 1
                short_name = filename if len(filename) <= 60 else filename[:57] + '...'
                line = f"{spinner_char} Scanning {processed_files} files | Elapsed: {elapsed_str} | Current: {short_name}"
                pad = ' ' * max(0, prev_print_len - len(line))
                print(f"\r{line}{pad}", end='', flush=True)
                prev_print_len = len(line)
                last_print_time = now

            filepath = os.path.join(root, filename)
            file_ext = Path(filename).suffix.lower()

            if file_ext in video_extensions:
                video_files += 1
                video_files_list.append(filepath)
                media_files.append(filepath)
                continue

            if file_ext in image_extensions:
                image_files.append(filepath)
                media_files.append(filepath)
            else:
                non_image_files += 1
                skipped_files_list.append(filepath)

    # After walk
    total_files_scanned = processed_files
    print()  # newline after scan spinner

    # Stage 2: extract EXIF dates in batch using exiftool for all media files
    exif_mapping = None
    # Track summary info about which method provided EXIF dates
    exif_batch_info = {'method': None, 'found': 0, 'duration': 0.0, 'per_file': 0}
    if media_files:
        t0 = time.time()
        # Request multiple date tags commonly used by images and videos
        exif_mapping = _run_exiftool_batch(media_files)
        t1 = time.time()
        if exif_mapping is not None:
            exif_batch_info.update({'method': 'exiftool', 'found': sum(1 for v in exif_mapping.values() if v), 'duration': t1 - t0, 'per_file': 0})
            # If there are videos without dates, try ffprobe for them
            missing_videos = [p for p in video_files_list if not exif_mapping.get(os.path.abspath(p))]
            if missing_videos and ffprobe_available():
                t2 = time.time()
                ffmap = build_video_mapping_ffprobe(missing_videos)
                t3 = time.time()
                ff_found = sum(1 for v in ffmap.values() if v)
                # Merge ffprobe results into exif_mapping
                for k, v in ffmap.items():
                    if v and not exif_mapping.get(k):
                        exif_mapping[k] = v
                exif_batch_info['found'] += ff_found
                exif_batch_info['duration'] += (t3 - t2)
                if ff_found:
                    exif_batch_info['method'] = 'exiftool+ffprobe'
                    print(f"  ffprobe fallback found {ff_found} dates in {t3 - t2:.2f}s")
        else:
            print("⚠ Batch exiftool failed; trying fast in-process Pillow fallback (threaded).")
            t0 = time.time()
            try:
                exif_mapping = build_exif_mapping_pillow(media_files)
                t1 = time.time()
                found = sum(1 for v in exif_mapping.values() if v)
                exif_batch_info.update({'method': 'pillow', 'found': found, 'duration': t1 - t0, 'per_file': 0})
                print(f"  Pillow fallback completed in {t1 - t0:.2f}s; found {found} dates.")
            except Exception:
                exif_mapping = None
                print("  Pillow fallback failed; will fall back to per-file exiftool extraction (slow).")

            # If pillow fallback worked for some videos, try ffprobe for remaining videos
            if exif_mapping:
                missing_videos = [p for p in video_files_list if not exif_mapping.get(os.path.abspath(p))]
                if missing_videos and ffprobe_available():
                    t2 = time.time()
                    ffmap = build_video_mapping_ffprobe(missing_videos)
                    t3 = time.time()
                    ff_found = sum(1 for v in ffmap.values() if v)
                    for k, v in ffmap.items():
                        if v and not exif_mapping.get(k):
                            exif_mapping[k] = v
                    exif_batch_info['found'] += ff_found
                    exif_batch_info['duration'] += (t3 - t2)
                    if ff_found:
                        exif_batch_info['method'] = (exif_batch_info['method'] or 'pillow') + '+ffprobe'
                        print(f"  ffprobe fallback found {ff_found} dates in {t3 - t2:.2f}s")

            # Determine which files still need per-file extraction
            if exif_mapping:
                missing = [p for p in media_files if not exif_mapping.get(os.path.abspath(p))]
            else:
                missing = media_files

            if missing:
                exif_batch_info['per_file'] = len(missing)
                print(f"  As a last resort, per-file exiftool will be run on {len(missing)} files (slow).")
            else:
                print("  No per-file exiftool calls needed.")
    else:
        # No media -> nothing to do
        exif_batch_info.update({'method': None, 'found': 0, 'duration': 0.0, 'per_file': 0})


    # Process each media file and determine categories
    processed_media = 0
    scan_media_start = time.time()
    for filepath in media_files:
        processed_media += 1
        # spinner for media processing
        now = time.time()
        if now - last_print_time >= update_interval:
            elapsed = now - scan_media_start
            m, s = divmod(int(elapsed), 60)
            h, m = divmod(m, 60)
            elapsed_str = f"{h:d}:{m:02d}:{s:02d}" if h > 0 else f"{m:d}:{s:02d}"
            spinner_char = spinner_chars[spinner_index % len(spinner_chars)]
            spinner_index += 1
            short_name = os.path.basename(filepath)
            short_name = short_name if len(short_name) <= 60 else short_name[:57] + '...'
            line = f"{spinner_char} Processing media: {processed_media}/{len(media_files)} | Elapsed: {elapsed_str} | Current: {short_name}"
            pad = ' ' * max(0, prev_print_len - len(line))
            print(f"\r{line}{pad}", end='', flush=True)
            prev_print_len = len(line)
            last_print_time = now

        try:
            abs_fp = os.path.abspath(filepath)
            date_taken = None
            if exif_mapping is not None:
                date_taken = exif_mapping.get(abs_fp)
            if date_taken is None:
                # Fallback to per-file extraction (slow)
                # For videos we can still call exiftool per-file, same as images
                date_taken = get_date_taken(filepath)

            if date_taken:
                match_result = dates_match_folder(date_taken, filepath)
                if match_result is False:
                    files_with_mismatched_date += 1
                    folder_year, folder_month = extract_date_from_path(filepath)
                    files_with_mismatched_date_list.append((filepath, date_taken, folder_year, folder_month))
                files_with_date += 1
                files_with_date_list.append((filepath, date_taken, False))
            else:
                # Try to infer date from filename first, then from folder
                filename_date = extract_date_from_filename(filepath)
                folder_year, folder_month = extract_date_from_path(filepath)
                if filename_date:
                    files_with_filename_date += 1
                    files_with_filename_date_list.append((filepath, filename_date, 'filename'))
                elif folder_year and folder_month:
                    folder_date = f"{folder_year}:{folder_month}:01 00:00:00"
                    files_with_folder_date += 1
                    files_with_folder_date_list.append((filepath, folder_date, True))
                else:
                    files_without_date += 1
                    files_without_date_list.append(filepath)
        except Exception as e:
            error_files += 1
            error_files_list.append((filepath, str(e)))

    # Finish spinner and show final times
    try:
        total_elapsed = time.time() - scan_start_time
        m, s = divmod(int(total_elapsed), 60)
        h, m = divmod(m, 60)
        elapsed_str = f"{h:d}:{m:02d}:{s:02d}" if h > 0 else f"{m:d}:{s:02d}"
        print(f"\r✓ Scan complete: {total_files_scanned} files scanned, {len(image_files)} images processed | Total Time: {elapsed_str}{' ' * 20}")
    except Exception:
        print()

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
        'with_filename_date': files_with_filename_date,
        'with_filename_date_list': files_with_filename_date_list,
        'with_mismatched_date_list': files_with_mismatched_date_list,
        'without_date_list': files_without_date_list,
        'skipped_files_list': skipped_files_list,
        'video_files_list': video_files_list,
        'error_files_list': error_files_list,
        'warning_files_list': warning_files_list,
        'exif_batch': exif_batch_info
    }

def move_files_with_date(files_with_date_list, destination_folder):
    """
    Move files with valid EXIF date taken to destination folder.
    If a file with the same name exists and has a different size,
    rename the source file by appending _dupN before the extension.
    If a file with the same name and size exists, move it to DuplicatePhotos folder.
    Returns lists of moved and skipped files.
    """
    moved_files = []
    skipped_files = []
    duplicate_folder = r"C:\Users\brian\Pictures\DuplicatePhotos"

    # Create destination folder if it doesn't exist
    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)
        print(f"Created destination folder: {destination_folder}")

    # Create duplicate folder if it doesn't exist
    if not os.path.exists(duplicate_folder):
        os.makedirs(duplicate_folder)
        print(f"Created duplicate folder: {duplicate_folder}")

    print(f"\nMoving {len(files_with_date_list)} files to {destination_folder}...")

    for filepath, date_taken, from_folder in files_with_date_list:
        filename = os.path.basename(filepath)
        dest_path = os.path.join(destination_folder, filename)

        if os.path.exists(dest_path):
            src_size = os.path.getsize(filepath)
            dest_size = os.path.getsize(dest_path)
            if src_size == dest_size:
                # Move to duplicate folder instead of skipping
                duplicate_path = os.path.join(duplicate_folder, filename)
                # If duplicate filename exists, append _dupN
                name, ext = os.path.splitext(filename)
                n = 1
                while os.path.exists(duplicate_path):
                    duplicate_path = os.path.join(duplicate_folder, f"{name}_dup{n}{ext}")
                    n += 1
                try:
                    shutil.move(filepath, duplicate_path)
                    moved_files.append((filepath, duplicate_path))
                    print(f"  MOVED TO DUPLICATE: {filename} -> {duplicate_path} (same size as destination)")
                except Exception as e:
                    skipped_files.append((filepath, duplicate_path, str(e)))
                    print(f"  ERROR: {filename} - {e}")
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
    default_dir = r"C:\CameraRollWork"
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

    # Print exiftool version info (if available)
    exif_ver = get_exiftool_version()
    if exif_ver:
        print(f"exiftool version: {exif_ver}")
    else:
        print("⚠ exiftool not found; batch EXIF extraction will be unavailable. Install exiftool for faster scans.")
    
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
    output_lines.append(f"Files with date from filename: {results.get('with_filename_date', 0)}")
    output_lines.append(f"Files WITHOUT any date:      {results['without_date']}")
    output_lines.append(f"Video files (skipped):       {results['video_files']}")
    output_lines.append(f"Non-image files (skipped):   {results['non_image']}")
    output_lines.append(f"Files with errors:           {results['error_files']}")
    output_lines.append(f"Files with warnings:         {results['warning_files']}")
    output_lines.append(f"Total image files:           {results['with_date'] + results['with_folder_date'] + results['without_date']}")
    output_lines.append("="*60)

    # Add EXIF batch summary if available
    batch = results.get('exif_batch')
    if batch:
        method = batch.get('method') or 'none'
        summary = f"EXIF summary: {method} - {batch.get('found',0)} dates in {batch.get('duration',0.0):.2f}s"
        if batch.get('per_file'):
            summary += f" (per-file calls: {batch.get('per_file')})"
        output_lines.append(summary)

    # Display results on screen
    for line in output_lines:
        print(line)
    # Also print a short summary for convenience
    if batch:
        print(f"\n{summary}")
    
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

        if results.get('with_filename_date_list'):
            output_lines.append("\n--- Files WITH Date from FILENAME ---")
            print("\n--- Files WITH Date from FILENAME ---")
            for filepath, date_taken, src in results['with_filename_date_list']:
                formatted_date = format_date_taken(date_taken, False)
                line = f"  🏷️ [{formatted_date}] {filepath}"
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
    
    # Offer to update EXIF DateTimeOriginal for files that have inferred dates (from filename or folder)
    inferred = []
    if results.get('with_filename_date'):
        inferred.extend(results.get('with_filename_date_list', []))
    if results.get('with_folder_date'):
        inferred.extend(results.get('with_folder_date_list', []))

    if inferred:
        print(f"\nFound {len(inferred)} files with inferred dates (filename/folder) but missing EXIF 'Date Taken'.")
        update_choice = input("Update EXIF 'Date Taken' for these files? (y/n): ").strip().lower()
        if update_choice == 'y':
            # show a short preview
            print('\nPreview (first 10):')
            for fp, date_val, src in inferred[:10]:
                print(f"  {fp}  ->  {date_val}  (source: {src})")
            confirm = input("Proceed to write EXIF DateTimeOriginal for these files? (y/n): ").strip().lower()
            if confirm == 'y':
                updated = []
                failed = []
                overwrite = input("Overwrite originals (no backup)? (y/n) [n]: ").strip().lower() == 'y'
                for fp, date_val, src in inferred:
                    success, out = set_date_taken_exif(fp, date_val, overwrite=overwrite)
                    if success:
                        updated.append((fp, date_val, out))
                    else:
                        failed.append((fp, date_val, out))
                # Save logs
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                if updated:
                    fn = f"files_exif_updated_{timestamp}.txt"
                    with open(fn, 'w', encoding='utf-8') as f:
                        f.write('Updated EXIF DateTimeOriginal:\n')
                        f.write(f'Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n')
                        f.write('='*60 + '\n\n')
                        for src_fp, d, out in updated:
                            f.write(f"Updated: {src_fp} -> {d}\n")
                    print(f"\n✓ EXIF updated for {len(updated)} files. Details saved to: {fn}")
                if failed:
                    fn2 = f"files_exif_failed_{timestamp}.txt"
                    with open(fn2, 'w', encoding='utf-8') as f:
                        f.write('Failed to update EXIF DateTimeOriginal:\n')
                        f.write(f'Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n')
                        f.write('='*60 + '\n\n')
                        for src_fp, d, err in failed:
                            f.write(f"Failed: {src_fp} -> {d}\n  Reason: {err}\n\n")
                    print(f"\n✗ EXIF update failed for {len(failed)} files. Details saved to: {fn2}")
                print('\nDone updating EXIF tags.')

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