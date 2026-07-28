#!/usr/bin/env python3
"""
Converts markdown files to PDF using WeasyPrint.
Creates nicely formatted PDFs with styling.
"""

from markdown import markdown
from weasyprint import HTML
from pathlib import Path
from dataclasses import dataclass


@dataclass
class PDFConfig:
    """Configuration for PDF generation."""

    page_margin: str = "0.5in"  # Page margins (top, right, bottom, left)
    body_padding: str = "0"  # Body padding (in addition to page margin)
    base_font_size: str = "11pt"  # Base font size for body text
    line_height: float = 1.4  # Line height multiplier

    # Heading 1 styling
    h1_size: str = "18pt"  # Heading 1 font size
    h1_margin_top: str = "20px"  # Heading 1 top margin
    h1_margin_bottom: str = "15px"  # Heading 1 bottom margin
    h1_padding_bottom: str = "10px"  # Heading 1 padding bottom

    # Heading 2 styling
    h2_size: str = "15pt"  # Heading 2 font size
    h2_margin_top: str = "18px"  # Heading 2 top margin
    h2_margin_bottom: str = "12px"  # Heading 2 bottom margin

    # Heading 3 styling
    h3_size: str = "13pt"  # Heading 3 font size
    h3_margin_top: str = "15px"  # Heading 3 top margin
    h3_margin_bottom: str = "8px"  # Heading 3 bottom margin


def md_to_pdf(md_file: str, pdf_file: str = None, config: PDFConfig = None) -> None:
    """
    Convert a markdown file to PDF.

    Args:
        md_file: Path to the markdown file
        pdf_file: Path for output PDF (defaults to same name with .pdf extension)
        config: PDFConfig object with style settings (uses defaults if None)
    """
    if config is None:
        config = PDFConfig()
    md_path = Path(md_file)

    if not md_path.exists():
        print(f"Error: {md_file} not found")
        return

    if pdf_file is None:
        pdf_file = md_path.with_suffix(".pdf")

    try:
        # Read markdown content
        with open(md_path, "r", encoding="utf-8") as f:
            md_content = f.read()

        # Convert markdown to HTML
        html_content = markdown(
            md_content, extensions=["tables", "fenced_code", "codehilite"]
        )

        # Create styled HTML document
        html_string = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                }}
                
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: {config.line_height};
                    color: #333;
                    font-size: {config.base_font_size};
                    padding: {config.body_padding};
                    background-color: #fff;
                }}
                
                h1 {{
                    color: #0066cc;
                    font-size: {config.h1_size};
                    border-bottom: 3px solid #0066cc;
                    padding-bottom: {config.h1_padding_bottom};
                    margin-top: {config.h1_margin_top};
                    margin-bottom: {config.h1_margin_bottom};
                    page-break-after: avoid;
                }}
                
                h2 {{
                    color: #0066cc;
                    font-size: {config.h2_size};
                    margin-top: {config.h2_margin_top};
                    margin-bottom: {config.h2_margin_bottom};
                    page-break-after: avoid;
                }}
                
                h3 {{
                    color: #333;
                    font-size: {config.h3_size};
                    margin-top: {config.h3_margin_top};
                    margin-bottom: {config.h3_margin_bottom};
                    page-break-after: avoid;
                }}
                
                p {{
                    margin: 8px 0;
                    text-align: justify;
                }}
                
                ul, ol {{
                    margin: 10px 0 10px 25px;
                }}
                
                li {{
                    margin: 5px 0;
                }}
                
                a {{
                    color: #0066cc;
                    text-decoration: none;
                }}
                
                a:hover {{
                    text-decoration: underline;
                }}
                
                code {{
                    background-color: #f4f4f4;
                    padding: 2px 4px;
                    border-radius: 3px;
                    font-family: 'Courier New', monospace;
                    font-size: 0.9em;
                }}
                
                pre {{
                    background-color: #f4f4f4;
                    border-left: 4px solid #0066cc;
                    padding: 10px;
                    border-radius: 4px;
                    overflow-x: auto;
                    margin: 12px 0;
                    font-family: 'Courier New', monospace;
                    font-size: 0.85em;
                    line-height: 1.4;
                }}
                
                pre code {{
                    background-color: transparent;
                    padding: 0;
                    border-radius: 0;
                }}
                
                blockquote {{
                    border-left: 4px solid #ddd;
                    padding-left: 12px;
                    margin: 12px 0;
                    color: #666;
                    font-style: italic;
                }}
                
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 12px 0;
                    font-size: 0.95em;
                }}
                
                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }}
                
                th {{
                    background-color: #0066cc;
                    color: white;
                }}
                
                tr:nth-child(even) {{
                    background-color: #f9f9f9;
                }}
                
                hr {{
                    border: none;
                    border-top: 2px solid #ddd;
                    margin: 20px 0;
                }}
                
                @page {{
                    margin: {config.page_margin};
                    @bottom-center {{
                        content: "Page " counter(page) " of " counter(pages);
                        font-size: 9px;
                        color: #999;
                    }}
                }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """

        # Generate PDF
        HTML(string=html_string).write_pdf(pdf_file)
        print(f"✓ Successfully generated: {pdf_file}")

    except Exception as e:
        print(f"Error converting {md_file}: {e}")


if __name__ == "__main__":
    # Default configuration (compact with smaller margins and fonts)
    default_config = PDFConfig()

    # Convert both combined documentation files
    md_to_pdf("VISION_COMBINED.md", config=default_config)
    md_to_pdf("ARCHITECTURE_COMBINED.md", config=default_config)

    # Example: Custom config for more compact PDFs
    # compact_config = PDFConfig(
    #     page_margin="0.4in",
    #     base_font_size="10pt",
    #     h1_size="16pt",
    #     h2_size="13pt",
    #     h3_size="11pt",
    #     line_height=1.3,
    # )
    # md_to_pdf("VISION_COMBINED.md", config=compact_config)
