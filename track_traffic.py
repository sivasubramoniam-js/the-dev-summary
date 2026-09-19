import os
import csv
import math
import requests

# GitHub repository in owner/repo format (e.g., sivasubramoniam-js/the-dev-summary)
REPO = os.environ.get("GITHUB_REPOSITORY")
TOKEN = os.environ.get("GITHUB_TOKEN")
CSV_FILE = "traffic.csv"
SVG_FILE = "traffic.svg"

def get_headers():
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28"
    }

def fetch_traffic_data():
    headers = get_headers()
    
    # 1. Fetch Views (per day)
    views_url = f"https://api.github.com/repos/{REPO}/traffic/views"
    views_resp = requests.get(views_url, headers=headers)
    views_data = views_resp.json() if views_resp.status_code == 200 else {"views": []}
    if views_resp.status_code != 200:
        print(f"Warning: Failed to fetch views (status {views_resp.status_code}): {views_resp.text}")

    # 2. Fetch Clones (per day)
    clones_url = f"https://api.github.com/repos/{REPO}/traffic/clones"
    clones_resp = requests.get(clones_url, headers=headers)
    clones_data = clones_resp.json() if clones_resp.status_code == 200 else {"clones": []}
    if clones_resp.status_code != 200:
        print(f"Warning: Failed to fetch clones (status {clones_resp.status_code}): {clones_resp.text}")

    return views_data, clones_data

def load_existing_csv():
    records = {}
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                date_key = row.get("Date", "").strip()
                if date_key:
                    records[date_key] = {
                        "Date": date_key,
                        "No. of Clones": int(row.get("No. of Clones", 0) or 0),
                        "Total Views": int(row.get("Total Views", 0) or 0),
                        "Unique Clones": int(row.get("Unique Clones", 0) or 0),
                        "Unique Views": int(row.get("Unique Views", 0) or 0)
                    }
    return records

def generate_interactive_svg(records):
    sorted_dates = sorted(records.keys())
    if not sorted_dates:
        return

    # Keep last 14 to 30 days for clean chart visualization
    display_dates = sorted_dates[-30:]
    data = [records[d] for d in display_dates]

    width = 900
    height = 400
    pad_left = 65
    pad_right = 45
    pad_top = 80
    pad_bottom = 55

    chart_w = width - pad_left - pad_right
    chart_h = height - pad_top - pad_bottom

    max_views = max([d["Total Views"] for d in data] + [1])
    max_clones = max([d["No. of Clones"] for d in data] + [1])
    max_val = max(max_views, max_clones)
    max_val = max(10, int(math.ceil(max_val * 1.2)))
    if max_val % 5 != 0:
        max_val += (5 - max_val % 5)

    n = len(data)
    step_x = chart_w / (n - 1) if n > 1 else chart_w

    # Calculate summary numbers
    total_views = sum(d["Total Views"] for d in data)
    total_clones = sum(d["No. of Clones"] for d in data)

    # Grid lines (4 horizontal grid lines)
    grid_lines_svg = []
    y_labels_svg = []
    for i in range(5):
        val = int(i * (max_val / 4))
        y = pad_top + chart_h - (val / max_val * chart_h)
        grid_lines_svg.append(f'<line class="grid-line" x1="{pad_left}" y1="{y:.1f}" x2="{pad_left + chart_w}" y2="{y:.1f}" />')
        y_labels_svg.append(f'<text class="axis-text" x="{pad_left - 12}" y="{y + 4:.1f}" text-anchor="end">{val}</text>')

    view_pts = []
    groups_svg = []
    x_labels_svg = []

    # Decide step for X axis labels to prevent overlap
    label_step = max(1, n // 10)

    for i, d in enumerate(data):
        x = pad_left + i * step_x
        y_view = pad_top + chart_h - (d["Total Views"] / max_val * chart_h)
        y_clone = pad_top + chart_h - (d["No. of Clones"] / max_val * chart_h)
        bar_h = chart_h - (y_clone - pad_top)
        
        view_pts.append((x, y_view))

        # X-axis label (MM/DD)
        short_date = d["Date"][5:] if len(d["Date"]) >= 10 else d["Date"]
        if i % label_step == 0 or i == n - 1:
            x_labels_svg.append(f'<text class="axis-text" x="{x:.1f}" y="{pad_top + chart_h + 22}" text-anchor="middle">{short_date}</text>')

        # Tooltip box
        tt_w = 150
        tt_h = 68
        tt_x = x - (tt_w / 2)
        if tt_x < 15:
            tt_x = 15
        elif tt_x + tt_w > width - 15:
            tt_x = width - tt_w - 15
            
        tt_y = min(y_view, y_clone) - tt_h - 12
        if tt_y < pad_top - 30:
            tt_y = min(y_view, y_clone) + 18

        hitbox_w = step_x if n > 1 else chart_w
        hitbox_x = x - (hitbox_w / 2) if n > 1 else pad_left

        group = f'''
        <g class="data-group">
            <rect class="hitbox" x="{hitbox_x:.1f}" y="{pad_top}" width="{hitbox_w:.1f}" height="{chart_h}" />
            <line class="guideline" x1="{x:.1f}" y1="{pad_top}" x2="{x:.1f}" y2="{pad_top + chart_h}" />
            <rect class="bar-clones" x="{x - 6:.1f}" y="{y_clone:.1f}" width="12" height="{bar_h:.1f}" rx="3" />
            <circle class="dot-views" cx="{x:.1f}" cy="{y_view:.1f}" r="4.5" />
            <g class="tooltip" transform="translate({tt_x:.1f}, {tt_y:.1f})">
                <rect class="tt-bg" width="{tt_w}" height="{tt_h}" rx="6" />
                <text class="tt-title" x="{tt_w/2}" y="17" text-anchor="middle">{d["Date"]}</text>
                <text class="tt-views" x="14" y="37">● Views: <tspan class="tt-val">{d["Total Views"]}</tspan> ({d["Unique Views"]} uniq)</text>
                <text class="tt-clones" x="14" y="55">■ Clones: <tspan class="tt-val">{d["No. of Clones"]}</tspan> ({d["Unique Clones"]} uniq)</text>
            </g>
        </g>
        '''
        groups_svg.append(group)

    path_d = ' '.join([f'{"M" if i==0 else "L"} {pt[0]:.1f} {pt[1]:.1f}' for i, pt in enumerate(view_pts)])
    area_d = path_d + f' L {view_pts[-1][0]:.1f} {pad_top + chart_h} L {view_pts[0][0]:.1f} {pad_top + chart_h} Z' if view_pts else ''

    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">
    <defs>
        <linearGradient id="viewGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#58a6ff" stop-opacity="0.35" />
            <stop offset="100%" stop-color="#58a6ff" stop-opacity="0.0" />
        </linearGradient>
        <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
            <feDropShadow dx="0" dy="4" stdDeviation="4" flood-color="#000000" flood-opacity="0.6" />
        </filter>
    </defs>
    <style>
        .bg {{ fill: #0d1117; stroke: #30363d; stroke-width: 1; rx: 8; }}
        .header-title {{ fill: #f0f6fc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 16px; font-weight: 700; }}
        .header-sub {{ fill: #8b949e; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 12px; }}
        .grid-line {{ stroke: #21262d; stroke-dasharray: 4,4; stroke-width: 1; }}
        .axis-text {{ fill: #8b949e; font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace; font-size: 11px; }}
        
        .line-views {{ fill: none; stroke: #58a6ff; stroke-width: 3; stroke-linecap: round; stroke-linejoin: round; }}
        .area-views {{ fill: url(#viewGradient); }}
        
        .bar-clones {{ fill: #238636; transition: fill 0.2s; opacity: 0.85; }}
        .dot-views {{ fill: #58a6ff; stroke: #0d1117; stroke-width: 2; transition: r 0.2s, fill 0.2s; }}
        
        .data-group {{ cursor: pointer; }}
        .data-group .hitbox {{ fill: transparent; }}
        .data-group .guideline {{ stroke: #58a6ff; stroke-width: 1; stroke-dasharray: 3,3; opacity: 0; transition: opacity 0.2s; }}
        
        .tooltip {{ opacity: 0; pointer-events: none; transition: opacity 0.15s ease-in-out; filter: url(#shadow); }}
        .tt-bg {{ fill: #161b22; stroke: #30363d; stroke-width: 1; }}
        .tt-title {{ fill: #f0f6fc; font-family: ui-monospace, SFMono-Regular, monospace; font-size: 11px; font-weight: 700; }}
        .tt-views {{ fill: #58a6ff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 11px; }}
        .tt-clones {{ fill: #3fb950; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 11px; }}
        .tt-val {{ font-weight: 700; fill: #ffffff; }}
        
        .data-group:hover .guideline {{ opacity: 0.7; }}
        .data-group:hover .dot-views {{ r: 6.5; fill: #79c0ff; }}
        .data-group:hover .bar-clones {{ fill: #3fb950; opacity: 1; }}
        .data-group:hover .tooltip {{ opacity: 1; }}
        
        .legend-text {{ fill: #c9d1d9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 12px; }}
    </style>

    <!-- Background Card -->
    <rect class="bg" width="{width}" height="{height}" />

    <!-- Header & Live Totals -->
    <text class="header-title" x="{pad_left}" y="36">📊 Repository Traffic Insights (Last {len(data)} Days)</text>
    <text class="header-sub" x="{pad_left}" y="56">Hover over any day for details • Total Views: {total_views} • Total Clones: {total_clones}</text>

    <!-- Legends -->
    <circle cx="{width - pad_right - 180}" cy="34" r="5" fill="#58a6ff" />
    <text class="legend-text" x="{width - pad_right - 168}" y="38">Views</text>
    
    <rect x="{width - pad_right - 90}" y="29" width="10" height="10" rx="2" fill="#238636" />
    <text class="legend-text" x="{width - pad_right - 74}" y="38">Clones</text>

    <!-- Grid lines -->
    {''.join(grid_lines_svg)}

    <!-- Axis Labels -->
    {''.join(y_labels_svg)}
    {''.join(x_labels_svg)}

    <!-- Views Area & Line -->
    <path class="area-views" d="{area_d}" />
    <path class="line-views" d="{path_d}" />

    <!-- Interactive Data Points & Tooltips -->
    {''.join(groups_svg)}
</svg>
'''
    with open(SVG_FILE, "w", encoding="utf-8") as f:
        f.write(svg_content)
    print(f"Successfully generated interactive vector chart: {SVG_FILE}")

def update_traffic():
    if not REPO or not TOKEN:
        print("Missing GITHUB_REPOSITORY or GITHUB_TOKEN environment variable.")
        # If running locally without token, still generate SVG if CSV exists
        records = load_existing_csv()
        if records:
            generate_interactive_svg(records)
        return

    records = load_existing_csv()
    views_data, clones_data = fetch_traffic_data()

    # Process Views
    for entry in views_data.get("views", []):
        raw_ts = entry.get("timestamp", "")
        date_str = raw_ts.split("T")[0]
        if not date_str:
            continue
        if date_str not in records:
            records[date_str] = {
                "Date": date_str,
                "No. of Clones": 0,
                "Total Views": 0,
                "Unique Clones": 0,
                "Unique Views": 0
            }
        records[date_str]["Total Views"] = entry.get("count", 0)
        records[date_str]["Unique Views"] = entry.get("uniques", 0)

    # Process Clones
    for entry in clones_data.get("clones", []):
        raw_ts = entry.get("timestamp", "")
        date_str = raw_ts.split("T")[0]
        if not date_str:
            continue
        if date_str not in records:
            records[date_str] = {
                "Date": date_str,
                "No. of Clones": 0,
                "Total Views": 0,
                "Unique Clones": 0,
                "Unique Views": 0
            }
        records[date_str]["No. of Clones"] = entry.get("count", 0)
        records[date_str]["Unique Clones"] = entry.get("uniques", 0)

    # Sort records by date ascending
    sorted_dates = sorted(records.keys())

    # Write back to CSV
    fieldnames = ["Date", "No. of Clones", "Total Views", "Unique Clones", "Unique Views"]
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for d in sorted_dates:
            writer.writerow(records[d])

    print(f"Successfully updated {CSV_FILE} with {len(sorted_dates)} day(s) of traffic data.")

    # Generate interactive SVG chart
    generate_interactive_svg(records)

if __name__ == "__main__":
    update_traffic()
