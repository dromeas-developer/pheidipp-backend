#!/usr/bin/env python3
"""
Combines all markdown files from docs/vision/ into a single consolidated markdown file.
Uses reading-order.md to determine file ordering.
"""

import re
from pathlib import Path
from datetime import datetime


def parse_reading_order(vision_dir: Path) -> list[Path]:
    """
    Parse reading-order.md to extract the ordered list of document paths.
    
    Args:
        vision_dir: Path to docs/vision directory
        
    Returns:
        List of Path objects in reading order
    """
    reading_order_file = vision_dir / "reading-order.md"
    
    if not reading_order_file.exists():
        print(f"Warning: {reading_order_file} not found, falling back to default ordering")
        return []
    
    ordered_files = []
    
    try:
        with open(reading_order_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Extract file paths from markdown links: [text](path/to/file.md)
        pattern = r'\[([^\]]+)\]\(([^)]+\.md)\)'
        matches = re.findall(pattern, content)
        
        for _, filepath in matches:
            file_path = vision_dir / filepath
            if file_path.exists():
                ordered_files.append(file_path)
    except Exception as e:
        print(f"Warning: Error parsing reading-order.md: {e}")
        return []
    
    return ordered_files


def combine_vision_docs(output_file: str = "VISION_COMBINED.md") -> None:
    """
    Combines all markdown files from docs/vision/ into a single file.
    Uses reading-order.md for document ordering.
    
    Args:
        output_file: Name of the output file (created in current directory)
    """
    vision_dir = Path("docs/vision")
    
    if not vision_dir.exists():
        print(f"Error: {vision_dir} directory not found")
        return
    
    # Parse reading-order.md for the document order
    md_files = parse_reading_order(vision_dir)
    
    if not md_files:
        print("Error: Could not extract file list from reading-order.md or file not found")
        return
    
    with open(output_file, "w") as outfile:
        # Write header
        outfile.write("# Pheidipp Vision - Combined Documentation\n\n")
        outfile.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        outfile.write("*Document order based on reading-order.md*\n\n")
        outfile.write("---\n\n")
        
        # Write content from each file in reading order
        for idx, md_file in enumerate(md_files):
            relative_path = md_file.relative_to(vision_dir)
            
            # Read and write file content
            try:
                with open(md_file, "r", encoding="utf-8") as infile:
                    content = infile.read().strip()
                    
                    # For root-level files (vision-index.md), include directly
                    if md_file.parent == vision_dir:
                        outfile.write(content)
                        outfile.write("\n\n---\n\n")
                    else:
                        # Create section header for subdirectory files
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
