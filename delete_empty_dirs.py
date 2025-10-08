import os

START_DIR = r'C:\Users\brian\Pictures\CameraRollWorkingCopy'

def delete_empty_dirs(start_dir):
    count = 0
    # Walk from bottom up so we can remove empty parent folders after children
    for root, dirs, files in os.walk(start_dir, topdown=False):
        if not dirs and not files:
            try:
                os.rmdir(root)
                print(f"Deleted empty directory: {root}")
                count += 1
            except Exception as e:
                print(f"Failed to delete {root}: {e}")
    print(f"\nTotal empty directories deleted: {count}")

if __name__ == "__main__":
    delete_empty_dirs(START_DIR)