# PhotoMove Project Instructions

## Project Overview

PhotoMove is a Python utility suite for organizing and migrating photo/video collections with EXIF metadata management. The project focuses on safely moving media files between directories while preserving or enhancing metadata (specifically DateTimeOriginal tags).

## Core Architecture Patterns

### File Processing Pipeline

All scripts follow a consistent pattern:

1. **Scan & Analyze**: Walk source directories to catalog files
2. **Log Generation**: Create detailed text logs before any operations
3. **Interactive Confirmation**: Require user approval before destructive operations
4. **Batch Processing**: Execute moves/modifications with error handling

### Directory Structure Convention

- **Source**: `C:\Users\brian\Pictures\CameraRollWorkingCopy` (working copy for processing)
- **Destination**: `C:\Users\brian\Pictures\iCloud Photos\Photos` (final organized location)
- Scripts expect this specific Windows path structure

### EXIF Metadata Workflows

- **Primary Tool**: ExifTool via subprocess calls (not Python EXIF libraries)
- **Key Pattern**: Always use `subprocess.run()` with specific ExifTool flags
- **Date Format**: `%Y:%m:%d %H:%M:%S` for DateTimeOriginal tags
- **Tag Counting**: Use `exiftool -j` for JSON output to count metadata richness

## Key Components

### move_with_folder_dates.py

Main migration script that extracts dates from folder structure (`YYYY/MM` pattern) and applies them as EXIF DateTimeOriginal when missing. Handles file collision detection and provides interactive deletion of exact duplicates.

### move_videos_by_date.py

Video-specific processor that syncs MediaCreateDate to DateTimeOriginal. Handles various date formats and AM/PM parsing.

### match_by_name_timestamp.py

Handles iOS exported files with `YYYYMMDD_HHMMSSmmm_iOS.<ext>` naming pattern. Matches files by timestamp and extension for deduplication.

### date_checker.py

Comprehensive metadata analyzer supporting HEIC files via pillow_heif. Extracts folder-based date patterns and validates EXIF data integrity.

## Critical Implementation Details

### ExifTool Integration

```python
# Standard pattern for reading dates
result = subprocess.run(
    ['exiftool', '-DateTimeOriginal', '-d', '%Y:%m:%d %H:%M:%S', filepath],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
)

# Standard pattern for writing dates
result = subprocess.run(
    ['exiftool', f'-DateTimeOriginal={date_str}', '-overwrite_original', filepath],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
)
```

### Logging Pattern

All scripts generate timestamped log files in the project root:

- `move_candidates.txt` - Files queued for processing
- `move_errors.txt` - Collision/error reports
- `videos_with_date_YYYYMMDD_HHMMSS.txt` - Video analysis results
- `mov_matches_log.txt` - Filename pattern matches

### Safety Mechanisms

- **Dry-run first**: Always log operations before execution
- **Collision detection**: Check destination file existence and compare sizes/metadata
- **Exact duplicate removal**: Match by file size AND EXIF tag count
- **Interactive prompts**: Require explicit confirmation for destructive operations

## Development Workflows

### Testing Changes

1. Work with small test directories first
2. Check generated log files before proceeding
3. Verify ExifTool availability: `exiftool -ver`
4. Test HEIC support: ensure `pillow_heif` installed

### Adding New File Processors

Follow the established pattern:

- Source/destination directory constants at top
- Separate functions for metadata extraction
- Log generation before any file operations
- Interactive confirmation loops
- Comprehensive error handling with file path context

### Windows-Specific Considerations

- Use raw strings (`r''`) for all Windows paths
- Handle timezone conversion for file timestamps
- PowerShell-compatible subprocess calls
- File locking awareness for EXIF operations
