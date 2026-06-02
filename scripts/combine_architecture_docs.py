#!/usr/bin/env python3
"""
Combines all markdown files from docs/architecture/ into a single consolidated markdown file.
Preserves directory structure as headers in the output.
"""

import os
from pathlib import Path
from datetime import datetime


def combine_architecture_docs(output_file: str = "ARCHITECTURE_COMBINED.md") -> None:
    """
    Combines all markdown files from docs/architecture/ into a single file.
    
    Args:
        output_file: Name of the output file (created in current directory)
    """
    arch_dir = Path("docs/architecture")
    
    if not arch_dir.exists():
        print(f"Error: {arch_dir} directory not found")
        return
    
    # Collect all markdown files with their relative paths
    all_md_files = sorted(arch_dir.rglob("*.md"))
    
    if not all_md_files:
        print("No markdown files found in docs/architecture/")
        return
    
    # Separate root-level index from other files
    index_file = arch_dir / "index.md"
    if index_file.exists():
        md_files = [index_file] + [f for f in all_md_files if f != index_file]
    else:
        md_files = all_md_files
    
    with open(output_file, "w") as outfile:
        # Write header only if no index file exists
        if index_file not in md_files or not index_file.exists():
            outfile.write(f"# Pheidipp Architecture - Combined Documentation\n\n")
            outfile.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            outfile.write("---\n\n")
        
        # Write content from each file
        for idx, md_file in enumerate(md_files):
            relative_path = md_file.relative_to(arch_dir)
            
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
    combine_architecture_docs()
