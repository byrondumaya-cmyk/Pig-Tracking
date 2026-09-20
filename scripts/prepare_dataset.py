import os
import argparse
import yaml
from pathlib import Path

# The classes we want to KEEP and their new IDs
TARGET_CLASSES = {
    "lying": 0,
    "standing": 1
}

def remap_dataset(dataset_dir: str):
    """
    Reads a YOLOv8 dataset directory (data.yaml), finds all .txt annotation files,
    and remaps the class IDs according to the old_to_new mapping.
    Drops any bounding boxes that do not match the target classes.
    """
    yaml_path = Path(dataset_dir) / "data.yaml"
    if not yaml_path.exists():
        print(f"Error: Could not find data.yaml in {dataset_dir}")
        return
        
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)
        
    old_classes = data.get("names", [])
    if isinstance(old_classes, dict):
        # Some yaml formats store names as a dict {0: 'class1', ...}
        old_classes = [old_classes[i] for i in sorted(old_classes.keys())]
        
    print(f"Original dataset classes: {old_classes}")
    
    id_mapping = {}
    for old_id, class_name in enumerate(old_classes):
        class_name_lower = class_name.lower().strip()
        if class_name_lower in TARGET_CLASSES:
            id_mapping[old_id] = TARGET_CLASSES[class_name_lower]
            
    print(f"Mapping rules: {id_mapping}")
    
    # Process all .txt files in the dataset (labels folders)
    processed_files = 0
    boxes_kept = 0
    boxes_dropped = 0
    
    for txt_file in Path(dataset_dir).rglob("*.txt"):
        if "labels" not in str(txt_file) or txt_file.name == "classes.txt" or "README" in txt_file.name:
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
        
    # Overwrite data.yaml with the new classes
    data["nc"] = 2
    data["names"] = ["lying", "standing"]
    
    with open(yaml_path, "w") as f:
        yaml.dump(data, f, sort_keys=False)
        
    print(f"Done! Processed {processed_files} label files.")
    print(f"Kept {boxes_kept} bounding boxes. Dropped {boxes_dropped} complex behaviors.")
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remap YOLOv8 dataset to lying, standing")
    parser.add_argument("--dir", type=str, required=True, help="Path to the dataset root folder")
    args = parser.parse_args()
    
    remap_dataset(args.dir)
