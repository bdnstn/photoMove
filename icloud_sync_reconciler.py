import os
import json
import subprocess
from datetime import datetime
from collections import defaultdict
import stat

PC_PHOTOS_DIR = r'C:\Users\brian\Pictures\iCloud Photos\Photos'
LOG_FILE = f'icloud_sync_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'

def check_icloud_status(filepath):
    """Check if file is cloud-only, downloaded, or has other iCloud attributes"""
    try:
        file_stats = os.stat(filepath)
        attributes = file_stats.st_file_attributes if hasattr(file_stats, 'st_file_attributes') else 0
        
        status = []
        if attributes & stat.FILE_ATTRIBUTE_OFFLINE:
            status.append("cloud-only")
        if attributes & 0x100000:  # FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS
            status.append("available-online")
        if attributes & 0x200000:  # FILE_ATTRIBUTE_RECALL_ON_OPEN
            status.append("syncing")
        if not status:
            status.append("downloaded")
            
        return ", ".join(status) if status else "unknown"
    except Exception as e:
        return f"error: {e}"

def is_accessible(filepath):
    """Test if file appears to be accessible without triggering download"""
    try:
        # Only check if file exists and get basic stats - don't read content
        stat_info = os.stat(filepath)
        # If file size is very small (< 1KB), it might be a placeholder
        if stat_info.st_size < 1024:
            return False
        # Check if we can get file attributes without reading content
        return os.path.exists(filepath) and stat_info.st_size > 0
    except (OSError, IOError, PermissionError):
        return False

def get_file_metadata(filepath):
    """Get basic file metadata including creation and modification times"""
    try:
        stat_info = os.stat(filepath)
        return {
            'size': stat_info.st_size,
            'created': datetime.fromtimestamp(stat_info.st_ctime),
            'modified': datetime.fromtimestamp(stat_info.st_mtime),
            'accessible': is_accessible(filepath)
        }
    except Exception as e:
        return {
            'size': 0,
            'created': None,
            'modified': None,
            'accessible': False,
            'error': str(e)
        }

def get_exif_date(filepath):
    """Get DateTimeOriginal from EXIF data if available - DISABLED to avoid downloads"""
    # DISABLED: ExifTool would trigger download of cloud-only files
    # Only enable this for files you know are already downloaded
    return None

def analyze_icloud_sync():
    """Analyze iCloud sync status and identify problem files"""
    print("Analyzing iCloud Photos sync status...")
    print(f"Scanning: {PC_PHOTOS_DIR}")
    
    # File categorization
    sync_status_counts = defaultdict(int)
    file_type_counts = defaultdict(int)
    problem_files = []
    large_files = []
    old_files = []
    inaccessible_files = []
    
    # Process all files
    total_files = 0
    total_size = 0
    
    print("Scanning files...")
    
    for root, _, files in os.walk(PC_PHOTOS_DIR):
        for filename in files:
            filepath = os.path.join(root, filename)
            total_files += 1
            
            if total_files % 1000 == 0:
                print(f"Processed {total_files:,} files...")
            
            # Get file extension
            _, ext = os.path.splitext(filename.lower())
            file_type_counts[ext] = file_type_counts.get(ext, 0) + 1
            
            # Check iCloud sync status
            sync_status = check_icloud_status(filepath)
            sync_status_counts[sync_status] += 1
            
            # Get file metadata
            metadata = get_file_metadata(filepath)
            total_size += metadata['size']
            
            # Identify potential problem files
            file_info = {
                'filename': filename,
                'filepath': filepath,
                'relative_path': os.path.relpath(filepath, PC_PHOTOS_DIR),
                'sync_status': sync_status,
                'size': metadata['size'],
                'created': metadata['created'],
                'modified': metadata['modified'],
                'accessible': metadata['accessible'],
                'extension': ext
            }
            
            # Check for various issues
            if not metadata['accessible']:
                inaccessible_files.append(file_info)
            
            if metadata['size'] > 100 * 1024 * 1024:  # Files > 100MB
                large_files.append(file_info)
            
            if metadata['created'] and metadata['created'].year < 2020:
                old_files.append(file_info)
            
            # Files that might have sync issues
            if sync_status in ['cloud-only', 'syncing'] or 'error' in sync_status:
                problem_files.append(file_info)
    
    print(f"\nScan complete! Processed {total_files:,} files")
    
    # Generate detailed report
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write("iCloud Photos Sync Analysis Report\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write(f"PC Directory: {PC_PHOTOS_DIR}\n")
        f.write("="*80 + "\n\n")
        
        # Overall summary
        f.write("OVERALL SUMMARY\n")
        f.write("-" * 40 + "\n")
        f.write(f"Total files found on PC: {total_files:,}\n")
        f.write(f"Total size: {total_size / (1024**3):.2f} GB\n")
        f.write(f"iCloud.com count: 38,923 photos + 560 videos = 39,483\n")
        f.write(f"Difference: {total_files - 39483:,} files\n\n")
        
        # Sync status breakdown
        f.write("SYNC STATUS BREAKDOWN\n")
        f.write("-" * 40 + "\n")
        for status, count in sorted(sync_status_counts.items()):
            percentage = (count / total_files) * 100
            f.write(f"{status}: {count:,} files ({percentage:.1f}%)\n")
        f.write("\n")
        
        # File type breakdown
        f.write("FILE TYPE BREAKDOWN\n")
        f.write("-" * 40 + "\n")
        for ext, count in sorted(file_type_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_files) * 100
            f.write(f"{ext or 'no extension'}: {count:,} files ({percentage:.1f}%)\n")
        f.write("\n")
        
        # Problem files analysis
        if problem_files:
            f.write(f"POTENTIAL SYNC ISSUES ({len(problem_files):,} files)\n")
            f.write("-" * 40 + "\n")
            for file_info in problem_files[:50]:  # First 50 problematic files
                f.write(f"File: {file_info['relative_path']}\n")
                f.write(f"Status: {file_info['sync_status']}\n")
                f.write(f"Size: {file_info['size']:,} bytes\n")
                f.write(f"Created: {file_info['created']}\n")
                f.write(f"Accessible: {file_info['accessible']}\n")
                f.write("-" * 20 + "\n")
            if len(problem_files) > 50:
                f.write(f"... and {len(problem_files) - 50:,} more files with sync issues\n")
            f.write("\n")
        
        # Inaccessible files
        if inaccessible_files:
            f.write(f"INACCESSIBLE FILES ({len(inaccessible_files):,} files)\n")
            f.write("-" * 40 + "\n")
            for file_info in inaccessible_files[:20]:
                f.write(f"File: {file_info['relative_path']}\n")
                f.write(f"Status: {file_info['sync_status']}\n")
                f.write(f"Size: {file_info['size']:,} bytes\n")
                f.write("-" * 20 + "\n")
            if len(inaccessible_files) > 20:
                f.write(f"... and {len(inaccessible_files) - 20:,} more inaccessible files\n")
            f.write("\n")
        
        # Large files
        if large_files:
            f.write(f"LARGE FILES (>100MB) ({len(large_files):,} files)\n")
            f.write("-" * 40 + "\n")
            large_files.sort(key=lambda x: x['size'], reverse=True)
            for file_info in large_files[:10]:
                f.write(f"File: {file_info['relative_path']}\n")
                f.write(f"Size: {file_info['size'] / (1024**2):.1f} MB\n")
                f.write(f"Status: {file_info['sync_status']}\n")
                f.write("-" * 20 + "\n")
            f.write("\n")
        
        # Recommendations
        f.write("RECOMMENDATIONS\n")
        f.write("-" * 40 + "\n")
        f.write("1. Files with 'cloud-only' or 'syncing' status may not be fully uploaded\n")
        f.write("2. Inaccessible files might be corrupted or have permission issues\n")
        f.write("3. Very large files might fail to sync or take longer\n")
        f.write("4. Check for duplicate files that might inflate the count\n")
        f.write("5. Some files might be in iCloud but not yet reflected in the web interface\n")
        f.write("6. Consider checking 'Recently Deleted' in iCloud Photos\n\n")
        
        # Next steps
        f.write("SUGGESTED NEXT STEPS\n")
        f.write("-" * 40 + "\n")
        f.write("1. Force sync by accessing some 'cloud-only' files\n")
        f.write("2. Check iCloud storage space and account status\n")
        f.write("3. Restart iCloud Photos sync in Windows settings\n")
        f.write("4. Look for files with unusual names or characters\n")
        f.write("5. Check if any files are outside normal date ranges\n")
    
    # Console summary
    print(f"\nANALYSIS COMPLETE")
    print("="*50)
    print(f"Total files on PC: {total_files:,}")
    print(f"iCloud.com shows: 39,483 items")
    print(f"Difference: {total_files - 39483:,} files")
    print(f"Files with sync issues: {len(problem_files):,}")
    print(f"Inaccessible files: {len(inaccessible_files):,}")
    print(f"Large files (>100MB): {len(large_files):,}")
    print(f"\nDetailed report saved to: {LOG_FILE}")
    
    return {
        'total_files': total_files,
        'problem_files': problem_files,
        'inaccessible_files': inaccessible_files,
        'large_files': large_files,
        'sync_status_counts': dict(sync_status_counts),
        'file_type_counts': dict(file_type_counts)
    }

def generate_file_list_for_manual_check():
    """Generate a list of files that might not be in iCloud for manual verification"""
    print("\nGenerating file list for manual iCloud verification...")
    
    check_list_file = f'manual_check_list_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
    
    sample_files = []
    file_count = 0
    
    print("Scanning files for manual verification sample...")
    
    for root, _, files in os.walk(PC_PHOTOS_DIR):
        for filename in files:
            file_count += 1
            
            # Only process photo/video files
            if any(filename.lower().endswith(ext) for ext in ['.jpg', '.heic', '.mov', '.mp4', '.jpeg', '.avi', '.png']):
                filepath = os.path.join(root, filename)
                metadata = get_file_metadata(filepath)
                
                # Take a sample: every 300th file that's larger than 1MB
                if (file_count % 300 == 0 and 
                    metadata['size'] > 1024 * 1024 and  # > 1MB
                    len(sample_files) < 200):  # Max 200 files
                    
                    sample_files.append({
                        'filename': filename,
                        'relative_path': os.path.relpath(filepath, PC_PHOTOS_DIR),
                        'size_mb': metadata['size'] / (1024**2),
                        'created': metadata['created'].strftime('%Y-%m-%d %H:%M') if metadata['created'] else 'Unknown',
                        'extension': os.path.splitext(filename)[1].lower()
                    })
            
            # Progress indicator
            if file_count % 10000 == 0:
                print(f"Processed {file_count:,} files, collected {len(sample_files)} samples...")
    
    print(f"Sample collection complete! Found {len(sample_files)} sample files from {file_count:,} total files")
    
    # Sort by creation date (newest first)
    sample_files.sort(key=lambda x: x['created'], reverse=True)
    
    # Write the results
    with open(check_list_file, 'w', encoding='utf-8') as f:
        f.write("Sample Files for Manual iCloud Verification\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write(f"Sample of {len(sample_files)} files from {file_count:,} total files\n")
        f.write("="*70 + "\n\n")
        f.write("INSTRUCTIONS:\n")
        f.write("1. Go to iCloud.com and log into Photos\n")
        f.write("2. Search for these filenames (without the extension) in iCloud Photos\n")
        f.write("3. If a file is NOT found in iCloud, it may not be properly synced\n")
        f.write("4. Focus on files from different years/months to get good coverage\n\n")
        f.write("TIP: Use Ctrl+F in iCloud Photos to search by filename\n")
        f.write("="*70 + "\n\n")
        
        current_year = None
        for i, file_info in enumerate(sample_files, 1):
            # Group by year for easier organization
            file_year = file_info['created'][:4] if file_info['created'] != 'Unknown' else 'Unknown'
            if file_year != current_year:
                current_year = file_year
                f.write(f"\n--- {current_year} FILES ---\n")
            
            # Remove extension for searching in iCloud
            name_without_ext = os.path.splitext(file_info['filename'])[0]
            
            f.write(f"{i:3d}. Search for: {name_without_ext}\n")
            f.write(f"     Full filename: {file_info['filename']}\n")
            f.write(f"     Path: {file_info['relative_path']}\n")
            f.write(f"     Size: {file_info['size_mb']:.1f} MB\n")
            f.write(f"     Created: {file_info['created']}\n")
            f.write(f"     Type: {file_info['extension']}\n")
            f.write("\n")
    
    print(f"Manual check list saved to: {check_list_file}")
    return check_list_file

def main():
    print("iCloud Photos Sync Reconciliation Tool")
    print("="*50)
    print("This tool will help identify differences between your PC")
    print("and iCloud Photos to find files that may not be syncing.")
    print("")
    print("⚠️  IMPORTANT: This tool is designed to NOT trigger downloads")
    print("   of cloud-only files. It only reads file system metadata.")
    print("")
    
    if not os.path.exists(PC_PHOTOS_DIR):
        print(f"Error: Directory not found: {PC_PHOTOS_DIR}")
        return
    
    confirm = input("Continue with analysis? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Analysis cancelled.")
        return
    
    # Main analysis
    results = analyze_icloud_sync()
    
    # Generate manual check list
    print("\n" + "="*50)
    generate_manual_check = input("Generate a file list for manual iCloud verification? (y/n): ").strip().lower()
    if generate_manual_check == 'y':
        generate_file_list_for_manual_check()
    
    print("\n" + "="*50)
    print("ANALYSIS COMPLETE")
    print("\nKey findings:")
    print(f"- Your PC has {results['total_files']:,} files")
    print(f"- iCloud.com shows 39,483 items")
    print(f"- Difference of {results['total_files'] - 39483:,} files needs investigation")
    
    if results['problem_files']:
        print(f"- {len(results['problem_files']):,} files have potential sync issues")
    
    if results['inaccessible_files']:
        print(f"- {len(results['inaccessible_files']):,} files are inaccessible")
    
    print(f"\nSee detailed report: {LOG_FILE}")

if __name__ == "__main__":
    main()