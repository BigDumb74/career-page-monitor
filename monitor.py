import os
import json
import hashlib
from playwright.sync_api import sync_playwright

TARGET_URL = "https://careers.paychex.com/careers/jobs?sortBy=relevance&page=1&tags1=Paycor&view=search&limit=100"
DATA_FILE = "last_state.json"

def scrape_jobs():
    with sync_playwright() as p:
        # Launch headless browser
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print(f"Navigating to target portal...")
        page.goto(TARGET_URL, wait_until="networkidle")
        
        # Explicitly wait for the dynamic job grid component to render its data
        # (Phenom layouts typically use job-card or role list selectors)
        try:
            page.wait_for_selector(".job-title, [data-ph-at-id='job-title']", timeout=10000)
        except Exception as e:
            print("Warning: Timed out waiting for job selectors. Testing raw content fallback.")

        # Extract the titles and unique identifiers of the active listings
        # We target both standard elements and common Phenom attribute tags
        jobs_data = page.evaluate("""() => {
            const cards = document.querySelectorAll('.job-title, [data-ph-at-id="job-title"]');
            return Array.from(cards).map(card => card.innerText.trim()).filter(Boolean);
        }""")
        
        browser.close()
        return sorted(list(set(jobs_data)))

def check_for_updates():
    current_jobs = scrape_jobs()
    
    if not current_jobs:
        print("No jobs found or failed to parse the page structure.")
        return

    print(f"Successfully found {len(current_jobs)} active Paycor listings.")
    
    # Generate a unique hash footprint of the current listings
    current_hash = hashlib.sha256(json.dumps(current_jobs).encode('utf-8')).hexdigest()
    
    # Load the previous footprint if it exists
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            old_data = json.load(f)
            old_hash = old_data.get("hash", "")
            old_jobs = old_data.get("jobs", [])
    else:
        old_hash = ""
        old_jobs = []

    # Compare structural fingerprints
    if current_hash != old_hash:
        print("🚨 Change detected in listings!")
        
        # Calculate exactly what changed to keep alerts clean
        new_postings = [j for j in current_jobs if j not in old_jobs]
        removed_postings = [j for j in old_jobs if j not in current_jobs]
        
        if new_postings:
            print(f"New Roles Opened: {new_postings}")
        if removed_postings:
            print(f"Roles Closed/Filled: {removed_postings}")
            
        # TODO: Add your webhook alert trigger right here
        
        # Save the updated state to file
        with open(DATA_FILE, 'w') as f:
            json.dump({"hash": current_hash, "jobs": current_jobs}, f)
    else:
        print("✅ No changes detected. Listings match previous state.")

if __name__ == "__main__":
    check_for_updates()