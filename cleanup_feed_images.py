import os
import json

DATA_DIR = "feeds"
SAMPLE_FILE = "sample.json"
NEWS_FILE = "news.json"

def cleanup_feed_images():
    """
    Cleans up image URLs in feed files by matching feedname from sample.json
    with source in the feed items. If extracted_image is "" in sample.json,
    any image URLs for those sources are removed (set to "").
    """
    if not os.path.exists(SAMPLE_FILE):
        print(f"Error: '{SAMPLE_FILE}' not found.")
        return

    # 1. Load sample.json and identify sources where extracted_image is empty
    try:
        with open(SAMPLE_FILE, "r", encoding="utf-8") as f:
            sample_data = json.load(f)
    except Exception as e:
        print(f"Error loading {SAMPLE_FILE}: {e}")
        return

    no_image_sources = set()
    for item in sample_data:
        if item.get("extracted_image") == "" or not item.get("extracted_image"):
            if "feedname" in item:
                no_image_sources.add(item["feedname"])

    print(f"Found {len(no_image_sources)} sources with empty extracted_image in {SAMPLE_FILE}.")

    # 2. Gather all feed files to process (news.json + feeds/feed-*.json)
    files_to_process = []
    if os.path.exists(NEWS_FILE):
        files_to_process.append(NEWS_FILE)

    if os.path.exists(DATA_DIR):
        for root, dirs, files in os.walk(DATA_DIR):
            for filename in files:
                if filename.startswith("feed-") and filename.endswith(".json"):
                    files_to_process.append(os.path.join(root, filename))

    print(f"Checking {len(files_to_process)} feed files for cleanup...")

    total_items_cleaned = 0
    files_modified = 0

    # 3. Process each feed file
    for file_path in sorted(files_to_process):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                items = json.load(f)

            if not isinstance(items, list):
                continue

            modified = False
            file_cleaned_count = 0

            for item in items:
                source = item.get("source")
                # Match feedname and source
                if source in no_image_sources:
                    if item.get("image") and item.get("image") != "":
                        item["image"] = ""
                        modified = True
                        file_cleaned_count += 1
                        total_items_cleaned += 1

            if modified:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(items, f, indent=2)
                files_modified += 1
                print(f"  Cleaned {file_cleaned_count} items in {file_path}")

        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    print("\n=== CLEANUP SUMMARY ===")
    print(f"Total files modified: {files_modified}")
    print(f"Total items cleaned (image removed): {total_items_cleaned}")

if __name__ == "__main__":
    cleanup_feed_images()
