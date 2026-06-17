import os
import shutil
import json

SOURCE_DIR = "/Users/mohamud/Downloads/terminalbench/official_tasks"
TARGET_DIR = "/Users/mohamud/Downloads/harnesseng/official_tasks"

def is_dir_empty(path):
    if not os.path.exists(path):
        return True
    # If it only contains .DS_Store, treat it as empty
    items = [item for item in os.listdir(path) if item != ".DS_Store"]
    return len(items) == 0

def main():
    if not os.path.exists(SOURCE_DIR):
        print(f"Error: Source directory {SOURCE_DIR} does not exist.")
        return
        
    if not os.path.exists(TARGET_DIR):
        os.makedirs(TARGET_DIR)

    # 1. Get all task directories in source
    source_items = sorted(os.listdir(SOURCE_DIR))
    source_tasks = []
    for item in source_items:
        src_path = os.path.join(SOURCE_DIR, item)
        if os.path.isdir(src_path) and not item.startswith("."):
            # Ensure it has a task.toml or similar task marker
            if os.path.exists(os.path.join(src_path, "task.toml")):
                source_tasks.append(item)
                
    print(f"Found {len(source_tasks)} tasks in source directory: {SOURCE_DIR}")
    
    # 2. Get all task directories in target and check their status
    target_items = sorted(os.listdir(TARGET_DIR)) if os.path.exists(TARGET_DIR) else []
    target_tasks = []
    for item in target_items:
        tgt_path = os.path.join(TARGET_DIR, item)
        if os.path.isdir(tgt_path) and not item.startswith("."):
            target_tasks.append(item)
            
    print(f"Found {len(target_tasks)} directories in target: {TARGET_DIR}")
    
    # Check status of target tasks
    existing_non_empty = []
    existing_empty = []
    for task in target_tasks:
        tgt_path = os.path.join(TARGET_DIR, task)
        if is_dir_empty(tgt_path):
            existing_empty.append(task)
        else:
            existing_non_empty.append(task)
            
    print(f"\nTarget status:")
    print(f"  - Non-empty tasks ({len(existing_non_empty)}): {existing_non_empty}")
    print(f"  - Empty placeholders ({len(existing_empty)}): {existing_empty}")
    
    # 3. Determine tasks to pull
    # Remaining tasks are those in source that are either not in target or are empty in target.
    to_pull = []
    for task in source_tasks:
        tgt_path = os.path.join(TARGET_DIR, task)
        if task not in target_tasks or is_dir_empty(tgt_path):
            to_pull.append(task)
            
    print(f"\nTasks to pull ({len(to_pull)}):")
    # print(to_pull)
    
    # 4. Perform the copying
    copied_count = 0
    failed_count = 0
    for task in to_pull:
        src_path = os.path.join(SOURCE_DIR, task)
        tgt_path = os.path.join(TARGET_DIR, task)
        
        # If it was empty, clean it up first to avoid merge conflicts
        if os.path.exists(tgt_path):
            shutil.rmtree(tgt_path)
            
        try:
            shutil.copytree(src_path, tgt_path)
            copied_count += 1
            # print(f"Successfully pulled: {task}")
        except Exception as e:
            print(f"Failed to pull {task}: {e}")
            failed_count += 1
            
    print(f"\nPull complete:")
    print(f"  - Successfully pulled: {copied_count}")
    print(f"  - Failed to pull: {failed_count}")
    
    # Check final state
    final_items = sorted(os.listdir(TARGET_DIR))
    final_tasks = []
    for item in final_items:
        tgt_path = os.path.join(TARGET_DIR, item)
        if os.path.isdir(tgt_path) and not item.startswith(".") and os.path.exists(os.path.join(tgt_path, "task.toml")):
            final_tasks.append(item)
    print(f"Final count of valid tasks in target: {len(final_tasks)}")

if __name__ == "__main__":
    main()
