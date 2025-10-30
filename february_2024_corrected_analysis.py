#!/usr/bin/env python3
"""
CORRECTED February 2024 Analysis - Using EXIF Date Taken instead of file creation date
"""

import os
import sys
import subprocess
from datetime import datetime
from collections import defaultdict
import json

# Configuration
PC_PHOTOS_DIR = r'C:\Users\brian\Pictures\iCloud Photos\Photos'

def get_exif_date_taken(filepath):
    """
    Get the actual date taken from EXIF data (DateTimeOriginal)
    This is what iCloud Photos uses for organization
    """
    try:
        result = subprocess.run([
            'exiftool', '-DateTimeOriginal', '-d', '%Y:%m:%d %H:%M:%S', '-json', filepath
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if data and len(data) > 0:
                date_taken = data[0].get('DateTimeOriginal')
                if date_taken:
                    return datetime.strptime(date_taken, '%Y:%m:%d %H:%M:%S')
    except Exception:
        pass
    return None

def analyze_february_2024_corrected():
    """
    Corrected analysis using EXIF date taken instead of file creation date
    """
    print("Re-analyzing February 2024 files using EXIF Date Taken...")
    print("This will take longer as we need to read EXIF data from each file.")
    
    feb_2024_files = []
    processed_count = 0
    
    # First, find all files created in February 2024 (bulk import)
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
                
                # Filter for February 2024 (when files were imported to PC)
                if created.year == 2024 and created.month == 2:
                    processed_count += 1
                    
                    if processed_count % 1000 == 0:
                        print(f"Processed {processed_count:,} files...")
                    
                    # Get EXIF date taken
                    date_taken = get_exif_date_taken(filepath)
                    
                    feb_2024_files.append({
                        'filename': filename,
                        'filepath': filepath,
                        'size_mb': stat.st_size / (1024 * 1024),
                        'file_created': created,  # When imported to PC
                        'date_taken': date_taken,  # Actual photo date from EXIF
                        'extension': ext,
                        'relative_path': os.path.relpath(filepath, PC_PHOTOS_DIR)
                    })
                    
            except Exception as e:
                continue
    
    print(f"Found {len(feb_2024_files)} files imported in February 2024")
    print("Analyzing their actual date taken distribution...")
    
    # Analyze by actual date taken
    date_taken_distribution = defaultdict(int)
    files_with_exif = 0
    files_without_exif = 0
    extension_counts = defaultdict(int)
    
    for file_info in feb_2024_files:
        extension_counts[file_info['extension']] += 1
        
        if file_info['date_taken']:
            files_with_exif += 1
            # Group by year-month of actual photo date
            date_key = file_info['date_taken'].strftime('%Y-%m')
            date_taken_distribution[date_key] += 1
        else:
            files_without_exif += 1
    
    # Generate corrected report
    report_file = f'february_2024_corrected_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("CORRECTED February 2024 Analysis - By EXIF Date Taken\n")
        f.write("="*60 + "\n")
        f.write(f"Analysis Date: {datetime.now()}\n")
        f.write(f"Files imported in Feb 2024: {len(feb_2024_files):,}\n")
        f.write(f"Files with EXIF date: {files_with_exif:,}\n")
        f.write(f"Files without EXIF date: {files_without_exif:,}\n\n")
        
        f.write("KEY INSIGHT:\n")
        f.write("-" * 30 + "\n")
        f.write("These files were IMPORTED to your PC in Feb 2024,\n")
        f.write("but their actual PHOTO DATES span many years!\n")
        f.write("iCloud Photos organizes by photo date, not import date.\n\n")
        
        f.write("ACTUAL PHOTO DATES DISTRIBUTION:\n")
        f.write("-" * 40 + "\n")
        f.write("(This is how they appear in iCloud Photos timeline)\n\n")
        
        # Sort by date
        sorted_dates = sorted(date_taken_distribution.items())
        
        total_with_dates = sum(date_taken_distribution.values())
        f.write(f"Files with valid photo dates: {total_with_dates:,}\n")
        f.write(f"Files without photo dates: {files_without_exif:,}\n\n")
        
        f.write("Distribution by actual photo date:\n")
        for date_key, count in sorted_dates:
            percentage = (count / total_with_dates) * 100 if total_with_dates > 0 else 0
            f.write(f"{date_key}: {count:,} photos ({percentage:.1f}%)\n")
        
        f.write(f"\nFILE TYPES:\n")
        f.write("-" * 20 + "\n")
        for ext, count in sorted(extension_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(feb_2024_files)) * 100
            f.write(f"{ext:6}: {count:,} files ({percentage:.1f}%)\n")
        
        f.write(f"\nWHY THESE MAY NOT APPEAR IN iCLOUD:\n")
        f.write("="*40 + "\n")
        f.write("1. Files without EXIF dates may not sync properly\n")
        f.write("2. Very old photo dates might not display in timeline\n")
        f.write("3. Bulk import might have caused sync issues\n")
        f.write("4. Duplicate detection might have skipped some files\n")
        f.write("5. File naming patterns might affect sync\n\n")
        
        f.write("VERIFICATION STRATEGY:\n")
        f.write("="*30 + "\n")
        f.write("Instead of checking Feb 2024 in iCloud Photos,\n")
        f.write("check these date ranges where most photos were taken:\n\n")
        
        # Show top 10 photo date periods
        top_dates = sorted(date_taken_distribution.items(), key=lambda x: x[1], reverse=True)[:10]
        for date_key, count in top_dates:
            f.write(f"• {date_key}: {count:,} photos - Check this month in iCloud\n")
        
        if files_without_exif > 0:
            f.write(f"\nIMPORTANT: {files_without_exif:,} files have no EXIF date!\n")
            f.write("These might not sync to iCloud Photos properly.\n")
    
    print(f"Corrected analysis saved to: {report_file}")
    
    # Summary
    print(f"\nCORRECTED SUMMARY:")
    print(f"• Files imported in Feb 2024: {len(feb_2024_files):,}")
    print(f"• Files with EXIF dates: {files_with_exif:,}")
    print(f"• Files without EXIF dates: {files_without_exif:,}")
    
    if date_taken_distribution:
        top_month = max(date_taken_distribution.items(), key=lambda x: x[1])
        print(f"• Most photos were actually taken in: {top_month[0]} ({top_month[1]:,} photos)")
    
    return report_file

def suggest_verification_strategy():
    """
    Suggest how to verify these files in iCloud Photos using actual photo dates
    """
    print("\nVERIFICATION STRATEGY:")
    print("="*30)
    print("Now that we know these files span many years by photo date:")
    print("1. Go to iCloud.com Photos")
    print("2. Navigate to the year-months shown in the analysis")
    print("3. Count photos in those specific time periods")
    print("4. Compare with the expected counts from the analysis")
    print("5. Look for months that seem to have fewer photos than expected")

def main():
    print("CORRECTED February 2024 Investigation")
    print("="*50)
    print("Analyzing using EXIF Date Taken (not file creation date)")
    print("This is how iCloud Photos actually organizes photos!")
    print("")
    
    if not os.path.exists(PC_PHOTOS_DIR):
        print(f"Error: Directory not found: {PC_PHOTOS_DIR}")
        return
    
    # Check if ExifTool is available
    try:
        subprocess.run(['exiftool', '-ver'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: ExifTool is required but not found!")
        print("Please install ExifTool first.")
        return
    
    # Run corrected analysis
    report_file = analyze_february_2024_corrected()
    
    # Verification guidance
    suggest_verification_strategy()
    
    print(f"\nCORRECTED REPORT: {report_file}")
    print("\nThis should give us the real picture of where these photos")
    print("should appear in iCloud Photos timeline!")

if __name__ == "__main__":
    main()