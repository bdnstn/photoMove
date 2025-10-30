#!/usr/bin/env python3
"""
Alternative approaches to identify iCloud Photos sync discrepancies
Since iCloud.com doesn't show filenames, we need different strategies.
"""

import os
import sys
from datetime import datetime
from collections import defaultdict

# Configuration
PC_PHOTOS_DIR = r'C:\Users\brian\Pictures\iCloud Photos\Photos'

def analyze_by_date_and_count():
    """
    Analyze photos by date to identify patterns that might explain the discrepancy.
    This can help identify which time periods might have sync issues.
    """
    print("Analyzing photos by date to identify potential sync patterns...")
    
    date_analysis = defaultdict(lambda: {'count': 0, 'total_size_mb': 0, 'file_types': defaultdict(int)})
    
    total_files = 0
    
    for root, _, files in os.walk(PC_PHOTOS_DIR):
        for filename in files:
            filepath = os.path.join(root, filename)
            
            # Skip non-media files
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.heic', '.png', '.mov', '.mp4', '.avi', '.m4v']:
                continue
                
            total_files += 1
            
            try:
                stat = os.stat(filepath)
                created = datetime.fromtimestamp(stat.st_ctime)
                size_mb = stat.st_size / (1024 * 1024)
                
                # Group by year-month
                date_key = created.strftime('%Y-%m')
                
                date_analysis[date_key]['count'] += 1
                date_analysis[date_key]['total_size_mb'] += size_mb
                date_analysis[date_key]['file_types'][ext] += 1
                
            except Exception as e:
                print(f"Error processing {filename}: {e}")
    
    # Generate report
    report_file = f'date_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("iCloud Photos Date Analysis Report\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write(f"Total media files analyzed: {total_files:,}\n")
        f.write("="*70 + "\n\n")
        
        f.write("SUMMARY BY MONTH\n")
        f.write("This analysis can help identify:\n")
        f.write("- Time periods with unusually high file counts\n")
        f.write("- Months that might not be fully synced to iCloud\n")
        f.write("- File type distribution patterns\n\n")
        
        # Sort by date
        sorted_dates = sorted(date_analysis.items())
        
        f.write("Format: YYYY-MM | Files | Size (MB) | Top File Types\n")
        f.write("-" * 70 + "\n")
        
        yearly_totals = defaultdict(lambda: {'count': 0, 'size': 0})
        
        for date_key, data in sorted_dates:
            year = date_key[:4]
            yearly_totals[year]['count'] += data['count']
            yearly_totals[year]['size'] += data['total_size_mb']
            
            # Get top file types for this month
            top_types = sorted(data['file_types'].items(), key=lambda x: x[1], reverse=True)[:3]
            types_str = ', '.join([f"{ext}({count})" for ext, count in top_types])
            
            f.write(f"{date_key:7} | {data['count']:5,} | {data['total_size_mb']:8.1f} | {types_str}\n")
        
        f.write("\n" + "="*70 + "\n")
        f.write("YEARLY SUMMARY\n")
        f.write("-" * 70 + "\n")
        
        for year in sorted(yearly_totals.keys()):
            data = yearly_totals[year]
            f.write(f"{year}: {data['count']:,} files, {data['size']:.1f} MB\n")
        
        # Identify potential issues
        f.write("\n" + "="*70 + "\n")
        f.write("POTENTIAL SYNC ANALYSIS\n")
        f.write("-" * 70 + "\n")
        
        # Find months with unusually high counts (might indicate batch imports not synced)
        avg_monthly_count = total_files / len(sorted_dates) if sorted_dates else 0
        
        f.write(f"Average files per month: {avg_monthly_count:.1f}\n\n")
        
        f.write("Months with significantly above-average file counts:\n")
        f.write("(These might indicate bulk imports that may not be fully synced)\n\n")
        
        for date_key, data in sorted_dates:
            if data['count'] > avg_monthly_count * 2:  # More than double average
                f.write(f"• {date_key}: {data['count']:,} files ({data['count']/avg_monthly_count:.1f}x average)\n")
        
        f.write(f"\nTotal PC files: {total_files:,}\n")
        f.write(f"iCloud.com count: 39,483\n")
        f.write(f"Difference: {total_files - 39483:,} files\n")
        
        f.write("\nPOSSIBLE EXPLANATIONS FOR DISCREPANCY:\n")
        f.write("1. iCloud Photos may not count all file types the same way\n")
        f.write("2. Duplicate files or multiple versions may be counted differently\n")
        f.write("3. Some files may be in 'Recently Deleted' or not fully processed\n")
        f.write("4. Files with missing/invalid dates may not appear in iCloud Photos timeline\n")
        f.write("5. Very large files or certain formats may have sync issues\n")
    
    print(f"Date analysis report saved to: {report_file}")
    return report_file

def identify_large_files():
    """
    Identify very large files that might have sync issues
    """
    print("Identifying large files that might have sync issues...")
    
    large_files = []
    
    for root, _, files in os.walk(PC_PHOTOS_DIR):
        for filename in files:
            filepath = os.path.join(root, filename)
            
            # Skip non-media files
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.heic', '.png', '.mov', '.mp4', '.avi', '.m4v']:
                continue
            
            try:
                stat = os.stat(filepath)
                size_mb = stat.st_size / (1024 * 1024)
                
                # Flag files larger than 50MB
                if size_mb > 50:
                    large_files.append({
                        'filename': filename,
                        'size_mb': size_mb,
                        'created': datetime.fromtimestamp(stat.st_ctime),
                        'path': os.path.relpath(filepath, PC_PHOTOS_DIR)
                    })
            except Exception:
                continue
    
    # Sort by size
    large_files.sort(key=lambda x: x['size_mb'], reverse=True)
    
    report_file = f'large_files_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("Large Files Analysis\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write(f"Files larger than 50MB: {len(large_files)}\n")
        f.write("="*70 + "\n\n")
        
        f.write("VERIFICATION STRATEGY:\n")
        f.write("Since iCloud.com doesn't show filenames, try this approach:\n")
        f.write("1. Go to iCloud.com Photos\n")
        f.write("2. Navigate to the date when each large file was created\n")
        f.write("3. Look for files with similar sizes on that date\n")
        f.write("4. Large video files are easier to identify by duration\n\n")
        
        total_size = sum(f['size_mb'] for f in large_files)
        f.write(f"Total size of large files: {total_size:.1f} MB ({total_size/1024:.1f} GB)\n\n")
        
        for i, file_info in enumerate(large_files[:50], 1):  # Top 50 largest
            f.write(f"{i:2d}. {file_info['filename']}\n")
            f.write(f"    Size: {file_info['size_mb']:.1f} MB\n")
            f.write(f"    Date: {file_info['created'].strftime('%Y-%m-%d %H:%M')}\n")
            f.write(f"    Path: {file_info['path']}\n")
            f.write("\n")
    
    print(f"Large files report saved to: {report_file}")
    return report_file

def suggest_alternative_verification():
    """
    Suggest alternative ways to verify sync status
    """
    print("\nALTERNATIVE VERIFICATION STRATEGIES:")
    print("="*50)
    
    print("\n1. DATE-BASED VERIFICATION:")
    print("   • Go to iCloud.com Photos")
    print("   • Check specific dates from the date analysis report")
    print("   • Count photos on dates with high file counts")
    print("   • Compare with PC counts for those dates")
    
    print("\n2. FILE TYPE ANALYSIS:")
    print("   • Check if certain file types are missing")
    print("   • HEIC files might have different sync behavior")
    print("   • Video files (.MOV, .MP4) might sync differently")
    
    print("\n3. SIZE-BASED VERIFICATION:")
    print("   • Use the large files report to spot-check")
    print("   • Navigate to specific dates and look for large files")
    print("   • Video files are easier to identify by duration")
    
    print("\n4. STORAGE QUOTA CHECK:")
    print("   • Check iCloud storage usage vs. PC storage usage")
    print("   • If quotas don't match, some files may not be uploaded")
    
    print("\n5. RECENT FILES CHECK:")
    print("   • Check if recent photos (last 30 days) are syncing")
    print("   • This helps identify if sync is currently working")

def main():
    print("iCloud Photos Sync Analysis - Alternative Approach")
    print("="*60)
    print("Since iCloud.com doesn't show filenames, we'll use different")
    print("strategies to identify potential sync discrepancies.")
    print("")
    
    if not os.path.exists(PC_PHOTOS_DIR):
        print(f"Error: Directory not found: {PC_PHOTOS_DIR}")
        return
    
    print("Running comprehensive analysis...")
    
    # Run date analysis
    date_report = analyze_by_date_and_count()
    
    # Run large files analysis  
    large_files_report = identify_large_files()
    
    # Provide alternative strategies
    suggest_alternative_verification()
    
    print(f"\nREPORTS GENERATED:")
    print(f"• Date analysis: {date_report}")
    print(f"• Large files: {large_files_report}")
    
    print(f"\nNext steps:")
    print("1. Review the date analysis to identify time periods with high file counts")
    print("2. Use iCloud.com Photos to manually verify those specific dates")
    print("3. Check large files by navigating to their creation dates")
    print("4. Compare file counts between PC and iCloud for specific months")

if __name__ == "__main__":
    main()