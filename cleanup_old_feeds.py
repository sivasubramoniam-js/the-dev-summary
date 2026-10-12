import os
import json
import argparse
from datetime import datetime, timedelta

DATA_DIR = "feeds"
INDEX_FILE = os.path.join(DATA_DIR, "index.json")
DATE_FORMAT = "%d-%b-%Y"

def parse_date_from_filename(filename):
    d_str = filename.replace('feed-', '').replace('.json', '')
    try:
        return datetime.strptime(d_str, DATE_FORMAT)
    except Exception:
        return None

def clean_old_feeds(days=10):
    if not os.path.exists(DATA_DIR):
        print(f"Directory '{DATA_DIR}' not found.")
        return 0

    cutoff_date = datetime.now() - timedelta(days=days)
    print(f"Cleaning feeds older than {days} days (cutoff: {cutoff_date.strftime(DATE_FORMAT)})...")

    deleted_count = 0
    all_files = []

    for root, dirs, files in os.walk(DATA_DIR):
        for f in files:
            if f.startswith('feed-') and f.endswith('.json'):
                file_path = os.path.join(root, f)
                dt = parse_date_from_filename(f)
                if dt:
                    if dt < cutoff_date:
                        try:
                            os.remove(file_path)
                            print(f"Deleted: {file_path}")
                            deleted_count += 1
                        except Exception as e:
                            print(f"Failed to delete {file_path}: {e}")
                    else:
                        rel_path = os.path.relpath(file_path, DATA_DIR).replace('\\', '/')
                        all_files.append((f, rel_path, dt))
                else:
                    rel_path = os.path.relpath(file_path, DATA_DIR).replace('\\', '/')
                    all_files.append((f, rel_path, datetime(2000, 1, 1)))

    # Remove empty directories in DATA_DIR
    for root, dirs, files in os.walk(DATA_DIR, topdown=False):
        for d in dirs:
            dir_path = os.path.join(root, d)
            try:
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    print(f"Removed empty directory: {dir_path}")
            except Exception:
                pass

    # Re-generate feeds/index.json
    all_files.sort(key=lambda x: x[2], reverse=True)
    index_data = []
    for filename, rel_path, _ in all_files:
        d_str = filename.replace('feed-', '').replace('.json', '')
        index_data.append({"date": d_str, "file": rel_path})

    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, indent=2)

    print(f"Cleanup complete. Deleted {deleted_count} files. Updated {INDEX_FILE} with {len(index_data)} entries.")
    return deleted_count

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Delete feeds older than specified days.")
    parser.add_argument("--days", type=int, default=10, help="Days threshold (default: 10)")
    args = parser.parse_args()
    clean_old_feeds(days=args.days)
