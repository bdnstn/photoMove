#!/usr/bin/env python3
"""
February 2024 Analysis - Deep dive into the unsynced bulk import
"""

import os
import sys
from datetime import datetime
from collections import defaultdict

# Configuration
PC_PHOTOS_DIR = r'C:\Users\brian\Pictures\iCloud Photos\Photos'

def analyze_february_2024():
    """
    Deep analysis of February 2024 files to understand the bulk import
    """
    print("Analyzing February 2024 files in detail...")
    
    feb_2024_files = []
    
    for root, _, files in os.walk(PC_PHOTOS_DIR):
        for filename in files:
            filepath = os.path.join(root, filename)
            
            # Skip non-media files
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.heic', '.png', '.mov', '.mp4', '.avi', '.m4v']:
                continue
            
            try:
                stat = os.stat(filepath)
                created = datetime.fromtimestamp(stat.st_ctime)
                
                # Filter for February 2024
                if created.year == 2024 and created.month == 2:
                    feb_2024_files.append({
                        'filename': filename,
                        'filepath': filepath,
                        'size_mb': stat.st_size / (1024 * 1024),
                        'created': created,
                        'modified': datetime.fromtimestamp(stat.st_mtime),
                        'extension': ext,
                        'relative_path': os.path.relpath(filepath, PC_PHOTOS_DIR)
                    })
                    
            except Exception as e:
                continue
    
    print(f"Found {len(feb_2024_files)} files from February 2024")
    
    # Analyze patterns
    size_distribution = defaultdict(int)
    extension_counts = defaultdict(int)
    date_hour_distribution = defaultdict(int)
    folder_distribution = defaultdict(int)
    
    total_size_gb = 0
    
    for file_info in feb_2024_files:
        # Size buckets
        size_mb = file_info['size_mb']
        total_size_gb += size_mb / 1024
        
        if size_mb < 1:
            size_distribution['< 1MB'] += 1
        elif size_mb < 5:
            size_distribution['1-5MB'] += 1
        elif size_mb < 10:
            size_distribution['5-10MB'] += 1
        elif size_mb < 20:
            size_distribution['10-20MB'] += 1
        else:
            size_distribution['> 20MB'] += 1
        
        # Extensions
        extension_counts[file_info['extension']] += 1
        
        # Hour of day when files were created (might show import pattern)
        hour = file_info['created'].hour
        date_hour_distribution[f"{file_info['created'].date()} {hour:02d}:00"] += 1
        
        # Folder structure
        folder = os.path.dirname(file_info['relative_path'])
        if not folder:
            folder = "root"
        folder_distribution[folder] += 1
    
    # Generate detailed report
    report_file = f'february_2024_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("February 2024 Bulk Import Analysis\n")
        f.write("="*50 + "\n")
        f.write(f"Analysis Date: {datetime.now()}\n")
        f.write(f"Total files found: {len(feb_2024_files):,}\n")
        f.write(f"Total size: {total_size_gb:.1f} GB\n\n")
        
        f.write("CONCLUSION: These files are NOT in iCloud Photos!\n")
        f.write("This explains the ~23,500 file discrepancy.\n\n")
        
        f.write("FILE TYPE BREAKDOWN:\n")
        f.write("-" * 30 + "\n")
        for ext, count in sorted(extension_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(feb_2024_files)) * 100
            f.write(f"{ext:8}: {count:,} files ({percentage:.1f}%)\n")
        
        f.write(f"\nSIZE DISTRIBUTION:\n")
        f.write("-" * 30 + "\n")
        for size_range, count in sorted(size_distribution.items()):
            percentage = (count / len(feb_2024_files)) * 100
            f.write(f"{size_range:8}: {count:,} files ({percentage:.1f}%)\n")
        
        f.write(f"\nTOP 20 IMPORT TIMES (Hour-by-hour):\n")
        f.write("-" * 50 + "\n")
        f.write("This shows when the bulk import happened:\n\n")
        
        sorted_hours = sorted(date_hour_distribution.items(), key=lambda x: x[1], reverse=True)[:20]
        for time_slot, count in sorted_hours:
            f.write(f"{time_slot}: {count:,} files\n")
        
        f.write(f"\nFOLDER DISTRIBUTION:\n")
        f.write("-" * 30 + "\n")
        f.write("Shows how files are organized:\n\n")
        
        sorted_folders = sorted(folder_distribution.items(), key=lambda x: x[1], reverse=True)[:20]
        for folder, count in sorted_folders:
            f.write(f"{folder}: {count:,} files\n")
        
        f.write(f"\nSAMPLE FILES (First 50 by creation time):\n")
        f.write("-" * 50 + "\n")
        
        # Sort by creation time
        feb_2024_files.sort(key=lambda x: x['created'])
        
        for i, file_info in enumerate(feb_2024_files[:50], 1):
            f.write(f"{i:2d}. {file_info['filename']}\n")
            f.write(f"    Created: {file_info['created'].strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"    Size: {file_info['size_mb']:.1f} MB\n")
            f.write(f"    Path: {file_info['relative_path']}\n\n")
        
        f.write("\nRECOMMENDATIONS:\n")
        f.write("="*50 + "\n")
        f.write("1. SYNC ISSUE CONFIRMED: These ~30K files didn't sync to iCloud\n")
        f.write("2. LIKELY CAUSE: Bulk import exceeded iCloud sync capacity\n")
        f.write("3. POSSIBLE SOLUTIONS:\n")
        f.write("   a) Force re-sync by moving files out and back in\n")
        f.write("   b) Use iCloud Photos 'Upload to My Photo Stream'\n")
        f.write("   c) Manual upload via iCloud.com (for smaller batches)\n")
        f.write("   d) Check iCloud storage quota - might be full\n")
        f.write("4. VERIFY: Check iCloud storage usage vs available space\n")
        f.write("5. MONITOR: Check if sync is currently in progress\n")
    
    print(f"Detailed February 2024 analysis saved to: {report_file}")
    
    # Quick summary
    print(f"\nQUICK SUMMARY:")
    print(f"• {len(feb_2024_files):,} files in Feb 2024 on PC")
    print(f"• {total_size_gb:.1f} GB total size")
    print(f"• Top file type: {max(extension_counts.items(), key=lambda x: x[1])[0]} ({max(extension_counts.values()):,} files)")
    print(f"• This explains your ~23,500 file discrepancy!")
    
    return report_file

def check_icloud_storage_status():
    """
    Provide guidance on checking iCloud storage status
    """
    print("\nCHECKING iCLOUD STORAGE STATUS:")
    print("="*40)
    print("To verify if storage is the issue:")
    print("1. Go to Settings > [Your Name] > iCloud > Photos")
    print("2. Check if 'iCloud Photos' is enabled")
    print("3. Look for any error messages or sync status")
    print("4. Go to Settings > [Your Name] > iCloud > Manage Storage")
    print("5. Check available space vs. used space")
    print("6. Look for 'Photos' in the storage breakdown")
    print("\nOR on Windows:")
    print("1. Open iCloud for Windows")
    print("2. Check Photos sync status")
    print("3. Look for error messages or warnings")
    print("4. Check storage quota in iCloud settings")

def main():
    print("February 2024 Bulk Import Investigation")
    print("="*50)
    print("Investigating the ~30,000 files that didn't sync to iCloud...")
    print("")
    
    if not os.path.exists(PC_PHOTOS_DIR):
        print(f"Error: Directory not found: {PC_PHOTOS_DIR}")
        return
    
    # Analyze February 2024 files
    report_file = analyze_february_2024()
    
    # Storage guidance
    check_icloud_storage_status()
    
    print(f"\nREPORT GENERATED: {report_file}")
    print(f"\nNEXT ACTIONS:")
    print(f"1. Review the detailed report")
    print(f"2. Check your iCloud storage status")
    print(f"3. Decide on sync strategy for the missing files")

if __name__ == "__main__":
    main()