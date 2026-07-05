import os
import json
import hashlib
from playwright.sync_api import sync_playwright

# Define the specific companies you want to track.
# You can add or remove companies here. If a company uses a different 
# CSS selector for its job titles, just add a custom 'selector' key.
MONITOR_CONFIG = {
    "Paycor": {
        "url": "https://careers.paychex.com/careers/jobs?sortBy=relevance&page=1&tags1=Paycor&view=search&limit=100",
        "selector": ".job-title, [data-ph-at-id='job-title']" # Phenom ATS
    },
    "ExampleCompany2": {
        "url": "https://boards.greenhouse.io/examplecompany2",
        "selector": ".opening a" # Greenhouse ATS standard selector
    }
}

DATA_FILE = "last_state.json"

def scrape_jobs(company_name, config):
    url = config["url"]
    # Fallback to a common default selector if one isn't specified
    selector = config.get("selector", ".job-title, h3, .opening-title") 
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print(f"[{company_name}] Navigating to career page...")
        try:
            page.goto(url, wait_until="networkidle", timeout=15000)
            
            # Wait for the specific job items to load
            page.wait_for_selector(selector, timeout=10000)
            
            # Extract text using the configured selector
            jobs_data = page.evaluate(f"""(sel) => {{
                const cards = document.querySelectorAll(sel);
                return Array.from(cards).map(card => card.innerText.trim()).filter(Boolean);
            }}""", selector)
            
        except Exception as e:
            print(f"Warning [{company_name}]: Page parsing hit an issue or timed out. Checking current visible text.")
            # Fallback evaluation attempt if the explicit selector fails
            jobs_data = page.evaluate(f"""(sel) => {{
                const cards = document.querySelectorAll(sel);
                return Array.from(cards).map(card => card.innerText.trim()).filter(Boolean);
            }}""", selector)
        
        browser.close()
        return sorted(list(set(jobs_data)))

def load_previous_state():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_current_state(state):
    with open(DATA_FILE, 'w') as f:
        json.dump(state, f, indent=4)

def check_for_updates():
    all_history = load_previous_state()
    new_history = {}
    
    for company_name, config in MONITOR_CONFIG.items():
        print(f"\n--- Checking {company_name} ---")
        current_jobs = scrape_jobs(company_name, config)
        
        if not current_jobs:
            print(f"[{company_name}] No jobs found or failed to parse.")
            # Retain old state if it failed so we don't accidentally wipe out historical alerts
            if company_name in all_history:
                new_history[company_name] = all_history[company_name]
            continue

        print(f"[{company_name}] Found {len(current_jobs)} active listings.")
        
        # Calculate unique hash for this specific company's list
        current_hash = hashlib.sha256(json.dumps(current_jobs).encode('utf-8')).hexdigest()
        
        # Pull company-specific historical data
        company_history = all_history.get(company_name, {})
        old_hash = company_history.get("hash", "")
        old_jobs = company_history.get("jobs", [])
        
        # Compare
        if current_hash != old_hash:
            if old_hash: # Don't alert on the very first script run when history is blank
                print(f"🚨 CHANGE DETECTED FOR {company_name.upper()}!")
                new_postings = [j for j in current_jobs if j not in old_jobs]
                removed_postings = [j for j in old_jobs if j not in current_jobs]
                
                if new_postings:
                    print(f"  ➡️ New Roles Opened: {new_postings}")
                if removed_postings:
                    print(f"  ❌ Roles Closed/Filled: {removed_postings}")
                
                # TODO: Trigger notification mechanics here
            else:
                print(f"✅ Initial state locked in for {company_name}.")
        else:
            print(f"✅ No changes detected for {company_name}.")
            
        # Update our tracking state object
        new_history[company_name] = {
            "hash": current_hash,
            "jobs": current_jobs
        }
        
    save_current_state(new_history)

if __name__ == "__main__":
    check_for_updates()