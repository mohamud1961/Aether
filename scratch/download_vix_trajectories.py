import urllib.request
import urllib.error
import re
import json
import time
import datetime as dt
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import RLock

# Constants
LEADERBOARD_URL = "https://www.tbench.ai/leaderboard/terminal-bench/2.0/vix/v0.1.22/claude-opus-4-7%40anthropic"
SYSTEM = "vix"
SYSTEM_VERSION = "v0.1.22"
MODEL = "claude-opus-4-7@anthropic"
ROOT = Path("/Users/mohamud/Downloads/harnesseng")
TARGET_DIR = ROOT / "research" / "sources" / "trajectories" / "vix"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
MAX_WORKERS = 10
TRIALS_PER_TASK_TARGET = 3

# Thread-safe logging and stats
print_lock = RLock()
stats = {
    "total_tasks": 0,
    "completed_tasks": 0,
    "failed_tasks": 0,
    "total_trials_downloaded": 0,
    "start_time": None
}

def log(msg):
    with print_lock:
        timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {msg}", flush=True)

def fetch_url(url, retries=3, backoff=1.5):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                body = resp.read()
                status = resp.status
                headers = dict(resp.headers.items())
                return body, status, headers
        except urllib.error.HTTPError as e:
            if e.code == 429:
                log(f"Rate limited (429) on {url}. Retrying after sleep...")
                time.sleep(5 * (attempt + 1))
            else:
                log(f"HTTPError {e.code} for {url} (Attempt {attempt+1}/{retries})")
                if attempt == retries - 1:
                    raise
                time.sleep(backoff ** attempt)
        except Exception as e:
            log(f"Error fetching {url}: {e} (Attempt {attempt+1}/{retries})")
            if attempt == retries - 1:
                raise
            time.sleep(backoff ** attempt)
    raise RuntimeError(f"Failed to fetch {url} after {retries} retries")

def parse_rsc_payload(html_content):
    calls = re.findall(r'self\.__next_f\.push\(\[([0-9]+),\s*"(.*?)"\]\)', html_content)
    full_payload = ""
    for num, val in calls:
        try:
            escaped_str = val.encode('utf-8').decode('unicode_escape')
            full_payload += escaped_str
        except Exception:
            pass
    return full_payload

def download_task(task_name, checksum):
    task_detail_url = f"{LEADERBOARD_URL}/{checksum}"
    task_subdir = TARGET_DIR / task_name
    task_subdir.mkdir(parents=True, exist_ok=True)
    
    task_record = {
        "task_name": task_name,
        "task_checksum": checksum,
        "n_trials_reported": 0,
        "avg_resolution_rate": 0.0,
        "success_count": 0,
        "task_dir": str(task_subdir),
        "task_detail_url": task_detail_url,
        "downloaded_files": [],
        "status": "pending",
        "reason": None,
        "fetched_at_utc": ""
    }
    
    try:
        # 1. Fetch Task Detail Page
        log(f"[{task_name}] Fetching task detail page...")
        detail_body, detail_status, detail_headers = fetch_url(task_detail_url)
        detail_html = detail_body.decode('utf-8', errors='replace')
        
        # Save task detail page
        (task_subdir / "task_detail_page.html").write_bytes(detail_body)
        (task_subdir / "task_detail_page.headers.json").write_text(json.dumps({
            "status": detail_status,
            "headers": detail_headers
        }, indent=2) + "\n")
        task_record["downloaded_files"].extend(["task_detail_page.html", "task_detail_page.headers.json"])
        
        # 2. Parse payload for trial IDs
        payload = parse_rsc_payload(detail_html)
        
        # Find all trial objects or trial IDs
        # Format in Next payload: {"trialId":"...", "trialName":"...", "reward":1, ...}
        # Let's extract trial metadata
        trial_matches = re.findall(r'\{[^{}]*?"trialId":"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"[^{}]*?\}', payload)
        
        trials = []
        seen_trial_ids = set()
        for match in trial_matches:
            try:
                # Add braces to make it valid JSON if needed, or parse via regex
                t_id = re.search(r'"trialId":"(.*?)"', match).group(1)
                if t_id in seen_trial_ids:
                    continue
                seen_trial_ids.add(t_id)
                
                reward_match = re.search(r'"reward":([0-9.]+)', match)
                reward = float(reward_match.group(1)) if reward_match else 0.0
                
                name_match = re.search(r'"trialName":"(.*?)"', match)
                t_name = name_match.group(1) if name_match else ""
                
                trials.append({
                    "id": t_id,
                    "name": t_name,
                    "reward": reward
                })
            except Exception:
                pass
                
        if not trials:
            # Fallback regex for raw UUIDs
            raw_uuids = re.findall(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', payload)
            for uuid in sorted(list(set(raw_uuids))):
                if uuid not in seen_trial_ids:
                    seen_trial_ids.add(uuid)
                    trials.append({
                        "id": uuid,
                        "name": f"{task_name}__fallback",
                        "reward": 1.0  # assume success or inspect later
                    })
        
        task_record["n_trials_reported"] = len(trials)
        if trials:
            successes = sum(1 for t in trials if t["reward"] >= 1.0)
            task_record["success_count"] = successes
            task_record["avg_resolution_rate"] = successes / len(trials)
            
        log(f"[{task_name}] Found {len(trials)} trials reported on page.")
        
        # Select target trials (first TRIALS_PER_TASK_TARGET, or up to available)
        target_trials = trials[:TRIALS_PER_TASK_TARGET]
        downloaded_trials = []
        
        for t_info in target_trials:
            t_id = t_info["id"]
            trial_url = f"{task_detail_url}/{t_id}"
            log(f"[{task_name}] Fetching trial page {t_id}...")
            
            t_body, t_status, t_headers = fetch_url(trial_url)
            
            html_filename = f"trial_{t_id}.html"
            headers_filename = f"trial_{t_id}.headers.json"
            
            (task_subdir / html_filename).write_bytes(t_body)
            (task_subdir / headers_filename).write_text(json.dumps({
                "status": t_status,
                "headers": t_headers
            }, indent=2) + "\n")
            
            task_record["downloaded_files"].extend([html_filename, headers_filename])
            downloaded_trials.append(t_id)
            
            with print_lock:
                stats["total_trials_downloaded"] += 1
                
        # 3. Write source_manifest.md for the task
        manifest_lines = [
            "# Source Manifest",
            "",
            f"- Task name: `{task_name}`",
            f"- Task checksum: `{checksum}`",
            f"- System: `{SYSTEM}`",
            f"- System version: `{SYSTEM_VERSION}`",
            f"- Model: `{MODEL}`",
            f"- Task detail source URL: {task_detail_url}",
            f"- Trials listed on task page: `{len(trials)}`",
            f"- Trials downloaded locally: `{len(downloaded_trials)}`",
            f"- Newly downloaded in this pass: {', '.join(f'`{tid}`' for tid in downloaded_trials)}",
            f"- Downloaded files: {', '.join(f'`{f}`' for f in sorted(task_record['downloaded_files']))}",
            f"- Trajectory completeness ({TRIALS_PER_TASK_TARGET}-per-task target): `{'complete' if len(downloaded_trials) >= min(TRIALS_PER_TASK_TARGET, len(trials)) else 'partial'}`",
            ""
        ]
        (task_subdir / "source_manifest.md").write_text("\n".join(manifest_lines))
        task_record["downloaded_files"].append("source_manifest.md")
        
        task_record["status"] = "complete"
        task_record["fetched_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
        
        with print_lock:
            stats["completed_tasks"] += 1
            log(f"[{task_name}] SUCCESSFUL (Task {stats['completed_tasks']}/{stats['total_tasks']})")
            
    except Exception as e:
        log(f"[{task_name}] FAILED to download: {e}")
        task_record["status"] = "failed"
        task_record["reason"] = str(e)
        with print_lock:
            stats["failed_tasks"] += 1
            
    return task_record

def main():
    stats["start_time"] = dt.datetime.now()
    log("=== Starting Vix Trajectory Acquisition (No-Browser Script) ===")
    
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Fetch the main leaderboard page
    log(f"Fetching main leaderboard page: {LEADERBOARD_URL}")
    leaderboard_body, leaderboard_status, leaderboard_headers = fetch_url(LEADERBOARD_URL)
    leaderboard_html = leaderboard_body.decode('utf-8', errors='replace')
    
    # Parse task details from self.__next_f.push
    rsc_payload = parse_rsc_payload(leaderboard_html)
    
    # Next RSC lists tasks as key-value JSON objects in arrays
    # Look for "taskName":"...", "taskChecksum":"..."
    task_names = re.findall(r'"taskName":"(.*?)"', rsc_payload)
    task_checksums = re.findall(r'"taskChecksum":"(.*?)"', rsc_payload)
    
    if not task_names or len(task_names) != len(task_checksums):
        log("Error: could not parse matching task names and checksums from leaderboard payload!")
        # Fallback raw payload search
        pairs = re.findall(r'"taskName":"(.*?)".*?"taskChecksum":"([0-9a-f]{64})"', rsc_payload)
        task_names = [p[0] for p in pairs]
        task_checksums = [p[1] for p in pairs]
        
    tasks = list(zip(task_names, task_checksums))
    # Deduplicate keeping order
    seen_checksums = set()
    deduped_tasks = []
    for t_name, t_sum in tasks:
        if t_sum not in seen_checksums:
            seen_checksums.add(t_sum)
            deduped_tasks.append((t_name, t_sum))
            
    stats["total_tasks"] = len(deduped_tasks)
    log(f"Identified {stats['total_tasks']} unique tasks to download.")
    
    # Save main leaderboard pages
    (TARGET_DIR / "leaderboard_page.html").write_bytes(leaderboard_body)
    (TARGET_DIR / "leaderboard_page.headers.json").write_text(json.dumps({
        "status": leaderboard_status,
        "headers": leaderboard_headers
    }, indent=2) + "\n")
    
    # 2. Run parallel download tasks using ThreadPoolExecutor
    task_records = []
    log(f"Launching ThreadPoolExecutor with {MAX_WORKERS} workers...")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_task = {
            executor.submit(download_task, name, checksum): (name, checksum)
            for name, checksum in deduped_tasks
        }
        
        for future in as_completed(future_to_task):
            record = future.result()
            task_records.append(record)
            
    # Sort task_records by task_name
    task_records.sort(key=lambda x: x["task_name"])
    
    # 3. Write download_manifest.json
    manifest = {
        "source_page": LEADERBOARD_URL,
        "system": SYSTEM,
        "system_version": SYSTEM_VERSION,
        "model": MODEL,
        "expected_task_count": stats["total_tasks"],
        "parsed_task_count": stats["total_tasks"],
        "complete_count": stats["completed_tasks"],
        "missing_count": stats["total_tasks"] - stats["completed_tasks"],
        "blocked_count": stats["failed_tasks"],
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "tasks": task_records
    }
    
    (TARGET_DIR / "download_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    log("Saved global download_manifest.json")
    
    # 4. Generate INDEX.md
    index_lines = [
        f"# {SYSTEM.capitalize()} Trajectory Corpus Index",
        "",
        f"- Source leaderboard: {LEADERBOARD_URL}",
        f"- Method: terminal-only extraction via leaderboard -> task checksum page -> trialId pages.",
        f"- Current target state tracked here: {TRIALS_PER_TASK_TARGET} trials per task.",
        "",
        "| Task | Checksum | Local Trial Count | Target | Status | Directory |",
        "|---|---|---|---|---|---|",
    ]
    
    for tr in task_records:
        local_count = len([f for f in tr["downloaded_files"] if f.startswith("trial_") and f.endswith(".html")])
        status = "complete" if local_count >= min(TRIALS_PER_TASK_TARGET, tr["n_trials_reported"]) else "partial"
        if tr["status"] == "failed":
            status = "failed"
        index_lines.append(
            f"| `{tr['task_name']}` | `{tr['task_checksum']}` | `{local_count}` | `{min(TRIALS_PER_TASK_TARGET, tr['n_trials_reported'])}` | `{status}` | `{tr['task_name']}` |"
        )
        
    (TARGET_DIR / "INDEX.md").write_text("\n".join(index_lines) + "\n")
    log("Saved global INDEX.md")
    
    # 5. Save missing or blocked report
    failed_tasks_report = [tr for tr in task_records if tr["status"] != "complete"]
    missing_lines = [
        "# Missing or Blocked Tasks Report",
        "",
        f"Total failed/blocked tasks in this sweep: {len(failed_tasks_report)}",
        ""
    ]
    if failed_tasks_report:
        missing_lines.append("| Task | Checksum | Error |")
        missing_lines.append("|---|---|---|")
        for ft in failed_tasks_report:
            missing_lines.append(f"| `{ft['task_name']}` | `{ft['task_checksum']}` | {ft['reason']} |")
            
    (TARGET_DIR / "missing_or_blocked_tasks.md").write_text("\n".join(missing_lines) + "\n")
    log("Saved missing_or_blocked_tasks.md")
    
    end_time = dt.datetime.now()
    duration = (end_time - stats["start_time"]).total_seconds()
    log(f"=== Sweep Complete! ===")
    log(f"Duration: {duration:.2f} seconds")
    log(f"Tasks parsed: {stats['total_tasks']}")
    log(f"Tasks successful: {stats['completed_tasks']}")
    log(f"Tasks failed: {stats['failed_tasks']}")
    log(f"Total trial pages downloaded: {stats['total_trials_downloaded']}")

if __name__ == "__main__":
    main()
