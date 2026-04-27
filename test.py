import os
import json

DATA_DIR = "feeds"

def find_empty_feeds():
    if not os.path.exists(DATA_DIR):
        print(f"Directory '{DATA_DIR}' not found.")
        return

    empty_feeds = []
    
    # Iterate through all files in the feeds directory
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".json"):
            file_path = os.path.join(DATA_DIR, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Check if the array length is 0
                    if isinstance(data, list) and len(data) == 0:
                        empty_feeds.append(filename)
            except Exception as e:
                print(f"Error reading {filename}: {e}")

    # Print filenames of empty feeds
    if empty_feeds:
        print(f"Found {len(empty_feeds)} empty feeds:")
        for feed in sorted(empty_feeds):
            print(feed)
    else:
        print("No empty feeds found.")

if __name__ == "__main__":
    find_empty_feeds()
