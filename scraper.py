import asyncio
import aiohttp
import feedparser
import json
import re
import os
from datetime import datetime, timedelta
import random

# Configuration
DATA_DIR = "feeds"
TEMP_DIR = "temp_feeds"
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

DATE_FORMAT = "%d-%b-%Y" # e.g. 02-May-2026
INDEX_FILE = os.path.join(DATA_DIR, "index.json")

# Limit concurrency
MAX_CONCURRENT_REQUESTS = 25
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

# List of all feeds
try:
    with open('feeds.json', 'r', encoding='utf-8') as f:
        FEEDS = json.load(f)
except Exception as e:
    print(f"Could not load feeds.json: {e}")
    FEEDS = []

async def fetch_url(session, url):
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36"
    }
    async with semaphore:
        try:
            async with session.get(url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    return await response.read()
                return None
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

def extract_image_from_entry(entry):
    # 1. Check media_content
    if 'media_content' in entry and entry.media_content:
        for media in entry.media_content:
            url = media.get('url')
            media_type = media.get('type', '')
            if url and ('image' in media_type or any(url.lower().split('?')[0].endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'])):
                return url
        if entry.media_content[0].get('url'):
            return entry.media_content[0].get('url')

    # 2. Check media_thumbnail
    if 'media_thumbnail' in entry and entry.media_thumbnail:
        url = entry.media_thumbnail[0].get('url')
        if url:
            return url

    # 3. Check enclosures / links
    if 'links' in entry:
        for link in entry.links:
            if link.get('rel') == 'enclosure' or 'image' in link.get('type', ''):
                url = link.get('href') or link.get('url')
                if url:
                    return url

    # 4. Extract from summary or content HTML
    html_content = entry.get('summary', '')
    if 'content' in entry and entry.content:
        for c in entry.content:
            html_content += " " + c.get('value', '')
    
    if html_content:
        img_tags = re.findall(r'<img\s+[^>]*?>', html_content, re.IGNORECASE)
        for tag in img_tags:
            for attr in ['src', 'data-src', 'data-original']:
                match = re.search(attr + r'=["\']([^"\']+)["\']', tag, re.IGNORECASE)
                if match:
                    src = match.group(1)
                    if src.startswith('http'):
                        return src

    return ""

async def get_link_preview(session, url):
    content = await fetch_url(session, url)
    if not content:
        return {"title": None, "description": None, "image": None, "url": url, "original_url": url, "textContent": ""}

    try:
        html = content.decode('utf-8', errors='ignore')
        meta_tags = re.findall(r'<meta\s+[^>]*?>', html, re.IGNORECASE)

        def get_meta(name):
            name_lower = name.lower()
            for tag in meta_tags:
                prop_match = re.search(r'(?:property|name)=["\']([^"\']+)["\']', tag, re.IGNORECASE)
                if prop_match and prop_match.group(1).lower() == name_lower:
                    content_match = re.search(r'content=["\']([^"\']*)["\']', tag, re.IGNORECASE)
                    if content_match:
                        return content_match.group(1)
            return None

        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else (get_meta("og:title") or "")
        description = get_meta("og:description") or get_meta("description") or ""
        og_url = get_meta("og:url") or url

        text_content = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', html, flags=re.IGNORECASE | re.DOTALL)
        text_content = re.sub(r'<[^>]+>', ' ', text_content)
        text_content = re.sub(r'\s+', ' ', text_content).strip()[:1000]

        preview = {
            "title": title,
            "description": description,
            "image": None,
            "url": og_url,
            "original_url": url,
            "textContent": text_content
        }
        return preview
    except Exception as e:
        print(f"Error parsing preview for {url}: {e}")
        return {"title": None, "description": None, "image": None, "url": url, "original_url": url, "textContent": ""}

def slugify(text):
    return re.sub(r'[-\s]+', '-', re.sub(r'[^\w\s-]', '', text.lower())).strip('-')

def get_existing_links(days=3):
    """Look through recent daily feeds to get existing links for deduplication."""
    links = set()
    for i in range(days):
        date_obj = datetime.now() - timedelta(days=i)
        date_str = date_obj.strftime(DATE_FORMAT)
        year_str = date_obj.strftime("%Y")
        month_str = date_obj.strftime("%b")
        day_str = date_obj.strftime("%d")
        path = os.path.join(DATA_DIR, year_str, month_str, day_str, f"feed-{date_str}.json")
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data:
                        if 'link' in item and item['link']:
                            links.add(item['link'])
            except:
                pass
    return links

async def fetch_feed(session, feed, existing_links, cutoff_timestamp):
    feed_url = feed.get('feedurl')
    feed_name = feed.get('feedname', 'Unknown Source')
    if not feed_url: return

    print(f"Phase 1 - Fetching : {feed_url}")
    
    content = await fetch_url(session, feed_url)
    if not content: return

    try:
        parsed = feedparser.parse(content)
        new_items = []
        now_ts = datetime.now().isoformat()

        for entry in parsed.entries:
            link = entry.get('link', '')
            if not link or link in existing_links:
                continue

            dt = entry.get('published_parsed')
            timestamp = datetime(*dt[:6]).isoformat() if dt else now_ts

            # Clamp future timestamps to current time
            if timestamp > now_ts:
                timestamp = now_ts

            # Skip items older than the freshness window
            if timestamp < cutoff_timestamp:
                continue
            
            item = {
                "title": entry.get('title', ''),
                "link": link,
                "description": entry.get('summary', ''),
                "image": extract_image_from_entry(entry),
                "datetimestamp": timestamp,
                "scraped_at": now_ts,
                "source": feed_name,
                "category": feed.get('category', 'General')
            }
            new_items.append(item)
        
        if new_items:
            temp_path = os.path.join(TEMP_DIR, f"{slugify(feed_name)}.json")
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(new_items[:50], f, indent=2)
            print(f"Phase 1 - Found {len(new_items)} new items for {feed_name}")
    except Exception as e:
        print(f"Error parsing feed {feed_name}: {e}")

async def process_temp_file(session, filename):
    temp_path = os.path.join(TEMP_DIR, filename)
    try:
        with open(temp_path, 'r', encoding='utf-8') as f:
            new_items = json.load(f)
        
        items_needing_preview = [
            item for item in new_items 
            if item.get('link') and (not item.get('title') or not item.get('description') or len(item['description']) < 50)
        ]
        print(f"Phase 2 - Processing previews for {len(items_needing_preview)}/{len(new_items)} items in: {filename}")
        preview_tasks = [get_link_preview(session, item['link']) for item in items_needing_preview]
        previews = await asyncio.gather(*preview_tasks)
        preview_map = {p.get('original_url', p['url']): p for p in previews}
        
        for item in new_items:
            preview = preview_map.get(item['link'])
            if preview:
                if preview.get('title') and not item.get('title'):
                    item['title'] = preview['title']
                if preview.get('description') and (not item.get('description') or len(item['description']) < 50):
                    item['description'] = preview['description']

        return new_items
    except Exception as e:
        print(f"Error Phase 2 processing {filename}: {e}")
        return []
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)

async def main_async():
    # 0. Cleanup and Prep
    for filename in os.listdir(TEMP_DIR):
        try: os.remove(os.path.join(TEMP_DIR, filename))
        except: pass

    existing_links = get_existing_links(days=3)
    cutoff_timestamp = (datetime.now() - timedelta(days=2)).isoformat()
    today_obj = datetime.now()
    today_str = today_obj.strftime(DATE_FORMAT)
    year_str = today_obj.strftime("%Y")
    month_str = today_obj.strftime("%b")
    day_str = today_obj.strftime("%d")
    today_file = os.path.join(DATA_DIR, year_str, month_str, day_str, f"feed-{today_str}.json")
    os.makedirs(os.path.dirname(today_file), exist_ok=True)

    # Use higher max header sizes to accommodate feeds with large headers (e.g. Notion)
    async with aiohttp.ClientSession(max_line_size=65536, max_field_size=65536) as session:
        # Phase 1: RSS Feeds
        print("--- Phase 1: RSS Feeds ---")
        await asyncio.gather(*(fetch_feed(session, feed, existing_links, cutoff_timestamp) for feed in FEEDS))
        
        # Phase 2: Link Previews
        print("--- Phase 2: Link Previews ---")
        temp_files = [f for f in os.listdir(TEMP_DIR) if f.endswith('.json')]
        results = await asyncio.gather(*(process_temp_file(session, f) for f in temp_files))
        
        all_new_items = []
        for batch in results:
            all_new_items.extend(batch)

    # Phase 3: Update Daily Feed
    print("--- Phase 3: Updating Daily Feed ---")
    today_data = []
    if os.path.exists(today_file):
        try:
            with open(today_file, 'r', encoding='utf-8') as f:
                today_data = json.load(f)
        except: pass

    # Filter out duplicates that might have slipped through
    today_links = {item['link'] for item in today_data}
    added_count = 0
    for item in all_new_items:
        if item['link'] not in today_links:
            today_data.append(item)
            today_links.add(item['link'])
            added_count += 1
    
    today_data.sort(key=lambda x: x['datetimestamp'], reverse=True)
    
    with open(today_file, 'w', encoding='utf-8') as f:
        json.dump(today_data, f, indent=2)
    print(f"Updated {today_file} with {added_count} new items (total: {len(today_data)}).")

    # Phase 4: Update Index and news.json
    print("--- Phase 4: Updating Index and news.json ---")
    all_files = []
    for root, dirs, files in os.walk(DATA_DIR):
        for f in files:
            if f.startswith('feed-') and f.endswith('.json'):
                rel_path = os.path.relpath(os.path.join(root, f), DATA_DIR).replace('\\', '/')
                all_files.append((f, rel_path))

    # Sort files by date (extracting date from filename)
    def extract_date(item):
        filename = item[0]
        try:
            d_str = filename.replace('feed-', '').replace('.json', '')
            return datetime.strptime(d_str, DATE_FORMAT)
        except:
            return datetime(2000, 1, 1)
    
    all_files.sort(key=extract_date, reverse=True)
    index_data = []
    for filename, rel_path in all_files:
        d_str = filename.replace('feed-', '').replace('.json', '')
        index_data.append({"date": d_str, "file": rel_path})
    
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, indent=2)

    # Determine latest feed data for news.json
    latest_feed_data = list(today_data)
    if not latest_feed_data and index_data:
        # Search backwards for the most recent NON-EMPTY feed file
        for entry in index_data:
            candidate_path = os.path.join(DATA_DIR, entry['file'])
            try:
                with open(candidate_path, 'r', encoding='utf-8') as f:
                    candidate_data = json.load(f)
                    if candidate_data:
                        latest_feed_data = candidate_data
                        break
            except:
                pass

    if latest_feed_data:
        shuffled_feed = list(latest_feed_data)
        random.shuffle(shuffled_feed)
        with open('news.json', 'w', encoding='utf-8') as f:
            json.dump(shuffled_feed, f, indent=2)
    else:
        print("Warning: No non-empty feed data found; keeping existing news.json.")

    # Phase 5: SEO Updates
    print("--- Phase 5: SEO Updates ---")
    current_date_str = datetime.now().strftime("%A, %B %d, %Y")
    iso_date = datetime.now().strftime("%Y-%m-%d")
    index_files = ['index.html', 'v1/index.html']
    
    feed_for_seo = today_data if today_data else latest_feed_data
    top_10 = [item for item in feed_for_seo if item.get('title')][:10]
    schema_items = []
    for i, item in enumerate(top_10):
        img = item['image'] if item.get('image') and item['image'].startswith('http') else "https://sivasubramoniam-js.github.io/the-dev-summary/logo.png"
        schema_items.append({
            "@type": "ListItem",
            "position": i + 1,
            "item": {
                "@type": "NewsArticle",
                "headline": item['title'],
                "url": item['link'],
                "datePublished": item['datetimestamp'],
                "image": img,
                "author": {"@type": "Organization", "name": item['source']},
                "publisher": {"@id": "https://sivasubramoniam-js.github.io/the-dev-summary/#organization"}
            }
        })

    for index_path in index_files:
        if os.path.exists(index_path):
            with open(index_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            content = re.sub(r'<title>.*?</title>', lambda m: f'<title>The Dev Summary | Tech News - {current_date_str}</title>', content)
            content = re.sub(r'<meta property="og:title" content=".*?">', lambda m: f'<meta property="og:title" content="The Dev Summary | News for {current_date_str}">', content)
            content = re.sub(r'<meta property="twitter:title" content=".*?">', lambda m: f'<meta property="twitter:title" content="The Dev Summary | News for {current_date_str}">', content)
            
            # Robust JSON-LD update using json parser to prevent malformed syntax
            blocks = list(re.finditer(r'<script type="application/ld\+json">(.*?)</script>', content, re.DOTALL))
            for b_match in blocks:
                if '"@graph"' in b_match.group(1):
                    try:
                        data = json.loads(b_match.group(1))
                        for node in data.get('@graph', []):
                            if node.get('@type') == 'ItemList' and node.get('name') == 'Top Tech Stories Today':
                                node['itemListElement'] = schema_items
                        new_json_str = '\n' + json.dumps(data, indent=4) + '\n    '
                        content = content[:b_match.start(1)] + new_json_str + content[b_match.end(1):]
                        break
                    except Exception as e:
                        print(f"Error updating JSON-LD in {index_path}: {e}")

            with open(index_path, 'w', encoding='utf-8') as f:
                f.write(content)

    sitemap_path = 'sitemap.xml'
    if os.path.exists(sitemap_path):
        with open(sitemap_path, 'r', encoding='utf-8') as f:
            sitemap_content = f.read()
        sitemap_content = re.sub(r'<lastmod>.*?</lastmod>', lambda m: f'<lastmod>{iso_date}</lastmod>', sitemap_content)
        with open(sitemap_path, 'w', encoding='utf-8') as f:
            f.write(sitemap_content)

    print("Completed successfully!")

if __name__ == "__main__":
    asyncio.run(main_async())