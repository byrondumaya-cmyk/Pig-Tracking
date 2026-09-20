import os
import argparse
from pathlib import Path

# The classes we want to KEEP and their new IDs
TARGET_CLASSES = {
    "lying": 0,
    "sitting": 1,
    "standing": 2
}

def remap_dataset(dataset_dir: str, class_map_file: str):
    """
    Reads a YOLO dataset directory, finds all .txt annotation files,
    and remaps the class IDs according to the old_to_new mapping.
    Drops any bounding boxes that do not match the target classes.
    """
    # 1. Read the old classes.txt
    old_classes = []
    class_file_path = Path(dataset_dir) / class_map_file
    if not class_file_path.exists():
        print(f"Error: Could not find {class_map_file} in {dataset_dir}")
        return
        
    with open(class_file_path, "r") as f:
        old_classes = [line.strip().lower() for line in f.readlines()]
        
    print(f"Original dataset classes: {old_classes}")
    
    # 2. Build mapping from Old ID -> New ID
    # e.g. If old classes are ["standing", "aggression", "lying"],
    # standing (0) -> 2, aggression (1) -> DROP, lying (2) -> 0
    id_mapping = {}
    for old_id, class_name in enumerate(old_classes):
        if class_name in TARGET_CLASSES:
            id_mapping[old_id] = TARGET_CLASSES[class_name]
            
    print(f"Mapping rules: {id_mapping}")
    
    # 3. Process all .txt files in the dataset
    processed_files = 0
    boxes_kept = 0
    boxes_dropped = 0
    
    for txt_file in Path(dataset_dir).rglob("*.txt"):
        if txt_file.name == class_map_file:
            continue
            
        with open(txt_file, "r") as f:
            lines = f.readlines()
            
        new_lines = []
        for line in lines:
            parts = line.strip().split()
            if not parts:
                continue
                
            old_id = int(parts[0])
            if old_id in id_mapping:
                new_id = id_mapping[old_id]
                new_lines.append(f"{new_id} {' '.join(parts[1:])}\n")
                boxes_kept += 1
            else:
                boxes_dropped += 1
                
        # Write back the filtered lines
        with open(txt_file, "w") as f:
            f.writelines(new_lines)
            
        processed_files += 1
        
    # 4. Overwrite classes.txt with the new classes
    with open(class_file_path, "w") as f:
        f.write("lying\nsitting\nstanding\n")
        
    print(f"Done! Processed {processed_files} files.")
    print(f"Kept {boxes_kept} bounding boxes. Dropped {boxes_dropped} complex behaviors.")
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remap YOLO dataset classes to lying, sitting, standing")
    parser.add_argument("--dir", type=str, required=True, help="Path to the dataset root folder")
    parser.add_argument("--classes", type=str, default="classes.txt", help="Name of the classes file")
    args = parser.parse_args()
    
    remap_dataset(args.dir, args.classes)
