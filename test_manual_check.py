#!/usr/bin/env python3
"""
Quick test script to test the manual check list generation
"""

import os
import sys
from datetime import datetime
import subprocess

# Same configuration as main script
PC_PHOTOS_DIR = r'C:\Users\brian\Pictures\iCloud Photos\Photos'

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

def get_exif_date(filepath):
    """Safely get EXIF date without triggering downloads"""
    # For this test, we'll skip EXIF reading to avoid potential downloads
    return None

def test_manual_check():
    """Test the manual check list generation with a small sample"""
    print("Testing manual check list generation...")
    
    check_list_file = f'manual_check_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
    
    suspicious_files = []
    file_count = 0
    processed_count = 0
    
    # Process only first 1000 files for testing
    for root, _, files in os.walk(PC_PHOTOS_DIR):
        for filename in files:
            if processed_count >= 1000:  # Limit for testing
                break
                
            filepath = os.path.join(root, filename)
            file_count += 1
            processed_count += 1
            
            if processed_count % 100 == 0:
                print(f"Processed {processed_count} files, found {len(suspicious_files)} candidates...")
            
            # Get file metadata first
            metadata = get_file_metadata(filepath)
            sync_status = check_icloud_status(filepath)
            
            # Generate a representative sample for manual verification
            # Focus on photo/video files larger than 1MB
            if (any(filename.lower().endswith(ext) for ext in ['.jpg', '.heic', '.mov', '.mp4']) and
                metadata['size'] > 1024 * 1024):  # Files larger than 1MB
                
                # Take every 10th qualifying file for testing (more frequent than 100th)
                if file_count % 10 == 0 and len(suspicious_files) < 50:
                    exif_date = get_exif_date(filepath)
                    
                    suspicious_files.append({
                        'filename': filename,
                        'relative_path': os.path.relpath(filepath, PC_PHOTOS_DIR),
                        'sync_status': sync_status,
                        'size_mb': metadata['size'] / (1024**2),
                        'created': metadata['created'].strftime('%Y-%m-%d') if metadata['created'] else 'Unknown',
                        'exif_date': exif_date or 'None'
                    })
        
        if processed_count >= 1000:
            break
    
    print(f"Found {len(suspicious_files)} files for manual check")
    
    # Write the results
    with open(check_list_file, 'w', encoding='utf-8') as f:
        f.write("Files for Manual iCloud Verification (TEST)\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write("="*60 + "\n\n")
        f.write("Instructions: Search for these files in iCloud.com Photos\n")
        f.write("to verify if they exist online.\n\n")
        
        for i, file_info in enumerate(suspicious_files, 1):
            f.write(f"{i:3d}. {file_info['filename']}\n")
            f.write(f"     Path: {file_info['relative_path']}\n")
            f.write(f"     Status: {file_info['sync_status']}\n")
            f.write(f"     Size: {file_info['size_mb']:.1f} MB\n")
            f.write(f"     Created: {file_info['created']}\n")
            f.write(f"     EXIF Date: {file_info['exif_date']}\n")
            f.write("\n")
    
    print(f"Test manual check list saved to: {check_list_file}")
    return check_list_file

if __name__ == "__main__":
    if not os.path.exists(PC_PHOTOS_DIR):
        print(f"Error: Directory not found: {PC_PHOTOS_DIR}")
        sys.exit(1)
    
    test_manual_check()