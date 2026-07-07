import os
import json
import shutil
from datetime import datetime

DATA_DIR = "feeds"
INDEX_FILE = os.path.join(DATA_DIR, "index.json")
DATE_FORMAT = "%d-%b-%Y"

def migrate_feeds():
    if not os.path.exists(DATA_DIR):
        print(f"Directory '{DATA_DIR}' not found.")
        return

    moved_count = 0
    all_files = []

    # 1. Walk through DATA_DIR and find all feed-*.json files
    for root, dirs, files in os.walk(DATA_DIR):
        for filename in files:
            if filename.startswith("feed-") and filename.endswith(".json"):
                old_path = os.path.join(root, filename)
                
                # Extract date string from filename
                d_str = filename.replace("feed-", "").replace(".json", "")
                try:
                    dt = datetime.strptime(d_str, DATE_FORMAT)
                except Exception as e:
                    print(f"Skipping {filename}: could not parse date ({e})")
                    continue

                year_str = dt.strftime("%Y")
                month_str = dt.strftime("%b")
                day_str = dt.strftime("%d")

                target_dir = os.path.join(DATA_DIR, year_str, month_str, day_str)
                new_path = os.path.join(target_dir, filename)

                if old_path != new_path:
                    os.makedirs(target_dir, exist_ok=True)
                    shutil.move(old_path, new_path)
                    moved_count += 1
                
                rel_path = os.path.relpath(new_path, DATA_DIR).replace('\\', '/')
                all_files.append((dt, d_str, rel_path))

    # Sort descending by date
    all_files.sort(key=lambda x: x[0], reverse=True)

    index_data = [{"date": item[1], "file": item[2]} for item in all_files]

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2)

    print(f"Migration complete! Moved {moved_count} files.")
    print(f"Updated {INDEX_FILE} with {len(index_data)} entries.")

if __name__ == "__main__":
    migrate_feeds()
