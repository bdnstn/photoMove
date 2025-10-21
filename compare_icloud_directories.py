import os
import shutil
import subprocess
import json
from datetime import datetime
from collections import defaultdict

DIR1 = r'C:\Users\brian\iCloudPhotos\Photos'
DIR2 = r'C:\Users\brian\Pictures\iCloud Photos\Photos'
BACKUP_DIR = r'C:\Users\brian\PictureBackup'
LOG_FILE = f'icloud_comparison_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'

def scan_directory(directory):
    """Scan directory and return dict of {filename_lower: [(original_filename, full_path, size), ...]}"""
    files_dict = defaultdict(list)
    
    if not os.path.exists(directory):
        print(f"Warning: Directory does not exist: {directory}")
        return files_dict
    
    for root, _, files in os.walk(directory):
        for filename in files:
            filepath = os.path.join(root, filename)
            try:
                file_size = os.path.getsize(filepath)
                # Use lowercase filename as key for case-insensitive comparison
                files_dict[filename.lower()].append((filename, filepath, file_size))
            except Exception as e:
                print(f"Error getting size for {filepath}: {e}")
    
    return files_dict

def count_exif_tags(filepath):
    """Count number of EXIF tags in file using ExifTool"""
    try:
        result = subprocess.run(
            ['exiftool', '-j', filepath],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore'
        )
        if result.returncode == 0:
            metadata = json.loads(result.stdout)[0]
            return len(metadata) - 1  # Subtract 1 for SourceFile
    except Exception:
        pass
    return 0

def compare_directories():
    """Compare files between two directories"""
    print(f"Scanning directory 1: {DIR1}")
    dir1_files = scan_directory(DIR1)
    
    print(f"Scanning directory 2: {DIR2}")
    dir2_files = scan_directory(DIR2)
    
    # Find common filenames
    common_filenames = set(dir1_files.keys()) & set(dir2_files.keys())
    
    same_size_count = 0
    same_size_files = []
    different_size_files = []
    multiple_matches = []
    
    print(f"\nFound {len(common_filenames)} files with matching names")
    print("Comparing file sizes...")
    
    for filename_lower in common_filenames:
        dir1_entries = dir1_files[filename_lower]
        dir2_entries = dir2_files[filename_lower]
        
        # Handle multiple files with same name in either directory
        if len(dir1_entries) > 1 or len(dir2_entries) > 1:
            multiple_matches.append({
                'filename_lower': filename_lower,
                'dir1_entries': dir1_entries,
                'dir2_entries': dir2_entries
            })
            continue
        
        # Single file in each directory
        dir1_original_name, dir1_path, dir1_size = dir1_entries[0]
        dir2_original_name, dir2_path, dir2_size = dir2_entries[0]
        
        if dir1_size == dir2_size:
            same_size_count += 1
            same_size_files.append({
                'filename_lower': filename_lower,
                'dir1_original_name': dir1_original_name,
                'dir2_original_name': dir2_original_name,
                'dir1_path': dir1_path,
                'dir2_path': dir2_path,
                'file_size': dir1_size
            })
        else:
            different_size_files.append({
                'filename_lower': filename_lower,
                'dir1_original_name': dir1_original_name,
                'dir2_original_name': dir2_original_name,
                'dir1_path': dir1_path,
                'dir1_size': dir1_size,
                'dir2_path': dir2_path,
                'dir2_size': dir2_size,
                'size_diff': abs(dir1_size - dir2_size)
            })
    
    # Calculate files only in one directory
    only_in_dir1 = set(dir1_files.keys()) - set(dir2_files.keys())
    only_in_dir2 = set(dir2_files.keys()) - set(dir1_files.keys())
    
    # Generate report
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(f"iCloud Photos Directory Comparison Report\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write(f"Directory 1: {DIR1}\n")
        f.write(f"Directory 2: {DIR2}\n")
        f.write("="*80 + "\n\n")
        
        # Summary
        f.write("SUMMARY\n")
        f.write("-" * 40 + "\n")
        f.write(f"Total files in Directory 1: {sum(len(entries) for entries in dir1_files.values())}\n")
        f.write(f"Total files in Directory 2: {sum(len(entries) for entries in dir2_files.values())}\n")
        f.write(f"Files with matching names: {len(common_filenames)}\n")
        f.write(f"Files with same name and size: {same_size_count} (not logged - identical)\n")
        f.write(f"Files with same name but different size: {len(different_size_files)}\n")
        f.write(f"Files with duplicate names in directories: {len(multiple_matches)}\n")
        f.write(f"Files only in Directory 1: {len(only_in_dir1)}\n")
        f.write(f"Files only in Directory 2: {len(only_in_dir2)} (not logged - not relevant for migration)\n\n")
        
        # Files with different sizes
        if different_size_files:
            f.write("FILES WITH DIFFERENT SIZES\n")
            f.write("-" * 40 + "\n")
            # Sort by size difference (largest first)
            different_size_files.sort(key=lambda x: x['size_diff'], reverse=True)
            
            for file_info in different_size_files:
                f.write(f"Filename (Dir1): {file_info['dir1_original_name']}\n")
                f.write(f"Filename (Dir2): {file_info['dir2_original_name']}\n")
                f.write(f"Dir1: {file_info['dir1_path']}\n")
                f.write(f"Dir1 Size: {file_info['dir1_size']:,} bytes\n")
                f.write(f"Dir2: {file_info['dir2_path']}\n")
                f.write(f"Dir2 Size: {file_info['dir2_size']:,} bytes\n")
                f.write(f"Size Difference: {file_info['size_diff']:,} bytes\n")
                f.write("-" * 40 + "\n")
        
        # Files with multiple matches
        if multiple_matches:
            f.write("\nFILES WITH DUPLICATE NAMES\n")
            f.write("-" * 40 + "\n")
            for match_info in multiple_matches:
                f.write(f"Filename (case-insensitive): {match_info['filename_lower']}\n")
                f.write("Directory 1 entries:\n")
                for original_name, path, size in match_info['dir1_entries']:
                    f.write(f"  {original_name} - {path} ({size:,} bytes)\n")
                f.write("Directory 2 entries:\n")
                for original_name, path, size in match_info['dir2_entries']:
                    f.write(f"  {original_name} - {path} ({size:,} bytes)\n")
                f.write("-" * 40 + "\n")
        
        # Only in one directory - log files only in dir1
        if only_in_dir1:
            f.write(f"\nFILES ONLY IN DIRECTORY 1 ({len(only_in_dir1)} files)\n")
            f.write("-" * 40 + "\n")
            for filename_lower in sorted(only_in_dir1):
                for original_name, path, size in dir1_files[filename_lower]:
                    f.write(f"{original_name} - {path} ({size:,} bytes)\n")
        
        # Files only in dir2 are suppressed from logging (not relevant for migration from dir1 to dir2)
    
    # Print summary to console
    print(f"\nCOMPARISON COMPLETE")
    print("="*50)
    print(f"Files with matching names: {len(common_filenames)}")
    print(f"Files with same name and size: {same_size_count}")
    print(f"Files with same name but different size: {len(different_size_files)}")
    print(f"Files with duplicate names: {len(multiple_matches)}")
    print(f"Files only in Dir1: {len(only_in_dir1)}")
    print(f"Files only in Dir2: {len(only_in_dir2)}")
    print(f"\nDetailed report saved to: {LOG_FILE}")
    
    return only_in_dir1, dir1_files, different_size_files, same_size_files

def move_files_to_dir2(only_in_dir1, dir1_files):
    """Move files that exist only in directory 1 to directory 2"""
    if not only_in_dir1:
        print("No files to move - all files exist in both directories or only in directory 2")
        return
    
    # Create move log
    move_log_file = f'move_from_dir1_to_dir2_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
    
    print(f"\nFound {len(only_in_dir1)} files that exist only in Directory 1")
    move = input("Do you want to move these files to Directory 2? (y/n): ").strip().lower()
    
    if move != 'y':
        print("Move operation cancelled")
        return
    
    moved_count = 0
    error_count = 0
    errors = []
    
    with open(move_log_file, 'w', encoding='utf-8') as f:
        f.write(f"Move Operation Log - Files from Dir1 to Dir2\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write(f"Source Directory: {DIR1}\n")
        f.write(f"Destination Directory: {DIR2}\n")
        f.write("="*80 + "\n\n")
        
        for filename_lower in sorted(only_in_dir1):
            for original_name, src_path, file_size in dir1_files[filename_lower]:
                dest_path = os.path.join(DIR2, original_name)
                
                try:
                    # Check if destination file now exists (safety check)
                    if os.path.exists(dest_path):
                        error_msg = f"Destination file already exists: {dest_path}"
                        print(f"SKIP: {error_msg}")
                        f.write(f"SKIPPED: {original_name}\n")
                        f.write(f"Source: {src_path}\n")
                        f.write(f"Reason: {error_msg}\n")
                        f.write("-" * 40 + "\n")
                        errors.append(error_msg)
                        error_count += 1
                        continue
                    
                    # Create destination directory if it doesn't exist
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    
                    # Move the file
                    shutil.move(src_path, dest_path)
                    moved_count += 1
                    
                    print(f"MOVED: {original_name}")
                    f.write(f"SUCCESS: {original_name}\n")
                    f.write(f"From: {src_path}\n")
                    f.write(f"To: {dest_path}\n")
                    f.write(f"Size: {file_size:,} bytes\n")
                    f.write("-" * 40 + "\n")
                    
                except Exception as e:
                    error_msg = f"Error moving {original_name}: {str(e)}"
                    print(f"ERROR: {error_msg}")
                    f.write(f"FAILED: {original_name}\n")
                    f.write(f"Source: {src_path}\n")
                    f.write(f"Destination: {dest_path}\n")
                    f.write(f"Error: {str(e)}\n")
                    f.write("-" * 40 + "\n")
                    errors.append(error_msg)
                    error_count += 1
        
        # Summary
        f.write(f"\nMOVE OPERATION SUMMARY\n")
        f.write("-" * 40 + "\n")
        f.write(f"Files successfully moved: {moved_count}\n")
        f.write(f"Files with errors: {error_count}\n")
        f.write(f"Total files processed: {moved_count + error_count}\n")
    
    print(f"\nMOVE OPERATION COMPLETE")
    print("="*50)
    print(f"Files successfully moved: {moved_count}")
    print(f"Files with errors: {error_count}")
    print(f"Move log saved to: {move_log_file}")
    
    if errors:
        print("\nErrors encountered:")
        for error in errors[:5]:  # Show first 5 errors
            print(f"  - {error}")
        if len(errors) > 5:
            print(f"  ... and {len(errors) - 5} more errors (see log file)")

def get_unique_filename(dest_dir, src_path, original_filename):
    """Generate a unique filename by adding a counter if file exists, preserving directory structure"""
    # Get the relative path from the source to preserve directory structure
    src_rel_path = os.path.relpath(src_path, DIR1)
    dest_base_path = os.path.join(dest_dir, os.path.dirname(src_rel_path))
    
    name, ext = os.path.splitext(original_filename)
    counter = 1
    
    while True:
        if counter == 1:
            new_filename = f"{name}_from_dir1{ext}"
        else:
            new_filename = f"{name}_from_dir1_{counter}{ext}"
        
        new_path = os.path.join(dest_base_path, new_filename)
        if not os.path.exists(new_path):
            return new_filename, new_path
        counter += 1

def move_different_size_files(different_size_files):
    """Move files with different sizes from dir1 to dir2 with unique names"""
    if not different_size_files:
        print("No files with different sizes to move")
        return
    
    # Create move log
    move_log_file = f'move_different_sizes_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
    
    print(f"\nFound {len(different_size_files)} files with different sizes between directories")
    print("These files will be copied to directory 2 with '_from_dir1' suffix to avoid overwriting")
    move = input("Do you want to move these files? (y/n): ").strip().lower()
    
    if move != 'y':
        print("Move operation cancelled")
        return
    
    moved_count = 0
    error_count = 0
    errors = []
    
    with open(move_log_file, 'w', encoding='utf-8') as f:
        f.write(f"Move Operation Log - Different Size Files from Dir1 to Dir2\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write(f"Source Directory: {DIR1}\n")
        f.write(f"Destination Directory: {DIR2}\n")
        f.write("="*80 + "\n\n")
        
        for file_info in different_size_files:
            src_path = file_info['dir1_path']
            original_filename = file_info['dir1_original_name']
            
            try:
                # Generate unique filename
                unique_filename, dest_path = get_unique_filename(DIR2, src_path, original_filename)
                
                # Create destination directory if needed
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                
                # Move the file (preserves metadata automatically)
                shutil.move(src_path, dest_path)
                moved_count += 1
                
                print(f"MOVED: {original_filename} -> {unique_filename}")
                f.write(f"SUCCESS: {original_filename}\n")
                f.write(f"From: {src_path}\n")
                f.write(f"To: {dest_path}\n")
                f.write(f"Original filename: {original_filename}\n")
                f.write(f"New filename: {unique_filename}\n")
                f.write(f"Source size: {file_info['dir1_size']:,} bytes\n")
                f.write(f"Existing file size in dir2: {file_info['dir2_size']:,} bytes\n")
                f.write(f"Size difference: {file_info['size_diff']:,} bytes\n")
                f.write("-" * 40 + "\n")
                
            except Exception as e:
                error_msg = f"Error copying {original_filename}: {str(e)}"
                print(f"ERROR: {error_msg}")
                f.write(f"FAILED: {original_filename}\n")
                f.write(f"Source: {src_path}\n")
                f.write(f"Error: {str(e)}\n")
                f.write("-" * 40 + "\n")
                errors.append(error_msg)
                error_count += 1
        
        # Summary
        f.write(f"\nMOVE OPERATION SUMMARY\n")
        f.write("-" * 40 + "\n")
        f.write(f"Files successfully copied: {moved_count}\n")
        f.write(f"Files with errors: {error_count}\n")
        f.write(f"Total files processed: {moved_count + error_count}\n")
    
    print(f"\nCOPY OPERATION COMPLETE")
    print("="*50)
    print(f"Files successfully copied: {moved_count}")
    print(f"Files with errors: {error_count}")
    print(f"Copy log saved to: {move_log_file}")
    
    if errors:
        print("\nErrors encountered:")
        for error in errors[:5]:  # Show first 5 errors
            print(f"  - {error}")
        if len(errors) > 5:
            print(f"  ... and {len(errors) - 5} more errors (see log file)")

def analyze_and_move_better_exif_files(same_size_files):
    """Analyze EXIF data for files with same name/size and move files with more EXIF data"""
    if not same_size_files:
        print("No files with same name and size to analyze for EXIF data")
        return
    
    print(f"\nAnalyzing EXIF data for {len(same_size_files)} files with matching names and sizes...")
    
    files_with_more_exif = []
    analysis_log_file = f'exif_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
    
    with open(analysis_log_file, 'w', encoding='utf-8') as f:
        f.write(f"EXIF Data Analysis - Files with Same Name and Size\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write(f"Directory 1: {DIR1}\n")
        f.write(f"Directory 2: {DIR2}\n")
        f.write("="*80 + "\n\n")
        
        for i, file_info in enumerate(same_size_files, 1):
            if i % 100 == 0:
                print(f"Analyzing file {i}/{len(same_size_files)}...")
            
            dir1_path = file_info['dir1_path']
            dir2_path = file_info['dir2_path']
            
            dir1_exif_count = count_exif_tags(dir1_path)
            dir2_exif_count = count_exif_tags(dir2_path)
            
            f.write(f"File: {file_info['dir1_original_name']}\n")
            f.write(f"Dir1 Path: {dir1_path}\n")
            f.write(f"Dir1 EXIF Tags: {dir1_exif_count}\n")
            f.write(f"Dir2 Path: {dir2_path}\n")
            f.write(f"Dir2 EXIF Tags: {dir2_exif_count}\n")
            
            if dir1_exif_count > dir2_exif_count:
                files_with_more_exif.append({
                    'file_info': file_info,
                    'dir1_exif_count': dir1_exif_count,
                    'dir2_exif_count': dir2_exif_count,
                    'exif_diff': dir1_exif_count - dir2_exif_count
                })
                f.write(f"RESULT: Dir1 has {dir1_exif_count - dir2_exif_count} more EXIF tags\n")
            elif dir2_exif_count > dir1_exif_count:
                f.write(f"RESULT: Dir2 has {dir2_exif_count - dir1_exif_count} more EXIF tags\n")
            else:
                f.write(f"RESULT: Both files have equal EXIF data\n")
            
            f.write("-" * 40 + "\n")
        
        # Summary
        f.write(f"\nEXIF ANALYSIS SUMMARY\n")
        f.write("-" * 40 + "\n")
        f.write(f"Total files analyzed: {len(same_size_files)}\n")
        f.write(f"Files where Dir1 has more EXIF data: {len(files_with_more_exif)}\n")
    
    print(f"EXIF analysis complete. Results saved to: {analysis_log_file}")
    
    if not files_with_more_exif:
        print("No files found where Directory 1 has more EXIF data than Directory 2")
        return
    
    print(f"\nFound {len(files_with_more_exif)} files where Directory 1 has more EXIF data")
    print(f"These files will OVERWRITE the corresponding files in Directory 2")
    print(f"Original Dir2 files will be moved to backup: {BACKUP_DIR}")
    overwrite = input("Do you want to proceed with the overwrite operation? (y/n): ").strip().lower()
    
    if overwrite != 'y':
        print("Overwrite operation cancelled")
        return
    
    # Create move log
    move_log_file = f'overwrite_better_exif_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
    
    moved_count = 0
    error_count = 0
    errors = []
    
    with open(move_log_file, 'w', encoding='utf-8') as f:
        f.write(f"Overwrite Operation Log - Files with Better EXIF Data\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write(f"Source Directory: {DIR1}\n")
        f.write(f"Destination Directory: {DIR2}\n")
        f.write("="*80 + "\n\n")
        
        for entry in files_with_more_exif:
            file_info = entry['file_info']
            src_path = file_info['dir1_path']
            dest_path = file_info['dir2_path']
            original_name = file_info['dir1_original_name']
            
            try:
                # Create backup directory structure if it doesn't exist
                rel_path = os.path.relpath(dest_path, DIR2)
                backup_path = os.path.join(BACKUP_DIR, f"overwrite_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}", rel_path)
                backup_dir = os.path.dirname(backup_path)
                os.makedirs(backup_dir, exist_ok=True)
                
                # Move original file to backup location (not copy, to avoid iCloud sync issues)
                shutil.move(dest_path, backup_path)
                
                # Copy the file with better EXIF data to destination
                shutil.copy2(src_path, dest_path)
                moved_count += 1
                
                print(f"OVERWRITTEN: {original_name}")
                f.write(f"SUCCESS: {original_name}\n")
                f.write(f"From: {src_path}\n")
                f.write(f"To: {dest_path}\n")
                f.write(f"Backup moved to: {backup_path}\n")
                f.write(f"Dir1 EXIF tags: {entry['dir1_exif_count']}\n")
                f.write(f"Dir2 EXIF tags: {entry['dir2_exif_count']}\n")
                f.write(f"EXIF difference: +{entry['exif_diff']} tags\n")
                f.write("-" * 40 + "\n")
                
            except Exception as e:
                error_msg = f"Error overwriting {original_name}: {str(e)}"
                print(f"ERROR: {error_msg}")
                f.write(f"FAILED: {original_name}\n")
                f.write(f"Source: {src_path}\n")
                f.write(f"Destination: {dest_path}\n")
                f.write(f"Error: {str(e)}\n")
                f.write("-" * 40 + "\n")
                errors.append(error_msg)
                error_count += 1
        
        # Summary
        f.write(f"\nOVERWRITE OPERATION SUMMARY\n")
        f.write("-" * 40 + "\n")
        f.write(f"Files successfully overwritten: {moved_count}\n")
        f.write(f"Files with errors: {error_count}\n")
        f.write(f"Total files processed: {moved_count + error_count}\n")
    
    print(f"\nOVERWRITE OPERATION COMPLETE")
    print("="*50)
    print(f"Files successfully overwritten: {moved_count}")
    print(f"Files with errors: {error_count}")
    print(f"Overwrite log saved to: {move_log_file}")
    
    if errors:
        print("\nErrors encountered:")
        for error in errors[:5]:  # Show first 5 errors
            print(f"  - {error}")
        if len(errors) > 5:
            print(f"  ... and {len(errors) - 5} more errors (see log file)")

def main():
    print("iCloud Photos Directory Comparison Tool")
    print("="*50)
    
    # Check if directories exist
    if not os.path.exists(DIR1):
        print(f"Error: Directory 1 does not exist: {DIR1}")
        return
    
    if not os.path.exists(DIR2):
        print(f"Error: Directory 2 does not exist: {DIR2}")
        return
    
    only_in_dir1, dir1_files, different_size_files, same_size_files = compare_directories()
    
    # Offer to move files that exist only in dir1 to dir2
    if only_in_dir1:
        move_files_to_dir2(only_in_dir1, dir1_files)
    
    # Offer to move files with different sizes
    if different_size_files:
        move_different_size_files(different_size_files)
    
    # Offer to analyze and overwrite files with better EXIF data
    if same_size_files:
        analyze_and_move_better_exif_files(same_size_files)

if __name__ == "__main__":
    main()