#!/usr/bin/env python3
"""
Non-interactive version of iCloud sync reconciler for testing
"""

import os
import sys
from datetime import datetime
import subprocess
from collections import defaultdict

# Configuration
PC_PHOTOS_DIR = r'C:\Users\brian\Pictures\iCloud Photos\Photos'
LOG_FILE = f'icloud_sync_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'

def check_icloud_status(filepath):
    """Check if a file is available locally or cloud-only using Windows file attributes"""
    try:
        result = subprocess.run(['powershell', '-Command', 
                               f'(Get-Item -Force -LiteralPath "{filepath}").Attributes'],
                               capture_output=True, text=True, check=True)
        attributes = result.stdout.strip()
        
        # Check for cloud/offline attributes
        if 'Offline' in attributes:
            return 'available-online'  # File exists but content is in cloud
        elif 'ReparsePoint' in attributes:
            return 'available-online'  # iCloud placeholder file
        else:
            return 'downloaded'  # File is locally available
    except Exception:
        return 'unknown'

def get_file_metadata(filepath):
    """Get basic file metadata"""
    try:
        stat = os.stat(filepath)
        return {
            'size': stat.st_size,
            'created': datetime.fromtimestamp(stat.st_ctime),
            'modified': datetime.fromtimestamp(stat.st_mtime)
        }
    except Exception as e:
        return {
            'size': 0,
            'created': None,
            'modified': None
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
    print("iCloud Photos Sync Reconciliation Tool (Auto Mode)")
    print("="*50)
    print("Generating manual verification list only...")
    print("")
    
    if not os.path.exists(PC_PHOTOS_DIR):
        print(f"Error: Directory not found: {PC_PHOTOS_DIR}")
        return
    
    # Generate manual check list directly
    generate_file_list_for_manual_check()
    
    print("\n" + "="*50)
    print("MANUAL CHECK LIST GENERATION COMPLETE")
    print("\nNext steps:")
    print("1. Open the generated manual check list file")
    print("2. Go to iCloud.com Photos")
    print("3. Search for the sample filenames to verify sync status")

if __name__ == "__main__":
    main()