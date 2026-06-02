#!/usr/bin/env python3
"""
Combines all markdown files from docs/vision/ into a single consolidated markdown file.
Preserves directory structure as headers in the output.
"""

import os
from pathlib import Path
from datetime import datetime


def combine_vision_docs(output_file: str = "VISION_COMBINED.md") -> None:
    """
    Combines all markdown files from docs/vision/ into a single file.
    
    Args:
        output_file: Name of the output file (created in current directory)
    """
    vision_dir = Path("docs/vision")
    
    if not vision_dir.exists():
        print(f"Error: {vision_dir} directory not found")
        return
    
    # Collect all markdown files with their relative paths
    all_md_files = sorted(vision_dir.rglob("*.md"))
    
    if not all_md_files:
        print("No markdown files found in docs/vision/")
        return
    
    # Custom sort: prioritize order (product, coach, twin) then alphabetically within each
    folder_order = {"product": 0, "coach": 1, "twin": 2}
    
    def sort_key(file_path):
        relative = file_path.relative_to(vision_dir)
        parts = relative.parts
        if len(parts) > 1:
            folder = parts[0]
            order = folder_order.get(folder, 999)
            return (order, str(relative))
        return (999, str(relative))
    
    md_files_sorted = sorted(all_md_files, key=sort_key)
    
    # Separate root-level index from other files
    index_file = vision_dir / "index.md"
    if index_file.exists():
        md_files = [index_file] + [f for f in md_files_sorted if f != index_file]
    else:
        md_files = md_files_sorted
    
    with open(output_file, "w") as outfile:
        # Write header only if no index file exists
        if index_file not in md_files or not index_file.exists():
            outfile.write(f"# Pheidipp Vision - Combined Documentation\n\n")
            outfile.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            outfile.write("---\n\n")
        
        # Write content from each file
        for idx, md_file in enumerate(md_files):
            relative_path = md_file.relative_to(vision_dir)
            
            # Read and write file content
            try:
                with open(md_file, "r", encoding="utf-8") as infile:
                    content = infile.read().strip()
                    
                    # For index file (first file), include it directly without section header
                    if idx == 0 and md_file.name == "index.md":
                        outfile.write(content)
                        outfile.write("\n\n---\n\n")
                    else:
                        # Create section header for other files
                        section_title = str(relative_path).replace(".md", "").replace("/", " > ")
                        outfile.write(f"## {section_title}\n\n")
                        outfile.write(content)
                        outfile.write("\n\n")
            except Exception as e:
                outfile.write(f"*Error reading file: {e}*\n\n")
        
        outfile.write("---\n")
        outfile.write("*End of combined documentation*\n")
    
    print(f"✓ Successfully combined {len(md_files)} markdown files")
    print(f"✓ Output written to: {output_file}")


if __name__ == "__main__":
    combine_vision_docs()
