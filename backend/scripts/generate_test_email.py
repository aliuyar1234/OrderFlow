#!/usr/bin/env python3
"""Test Email Generator for SMTP Ingest Testing.

Generates test emails with attachments for testing OrderFlow SMTP ingest.
Supports PDF, Excel, CSV attachments and plus-addressing for org routing.

Usage:
    # Generate email to stdout
    python scripts/generate_test_email.py --to orders+acme@orderflow.local \
        --from buyer@example.com --subject "PO 12345" \
        --attachment test.pdf

    # Send email via SMTP
    python scripts/generate_test_email.py --to orders+acme@orderflow.local \
        --from buyer@example.com --subject "PO 12345" \
        --attachment test.pdf --send --smtp-host localhost --smtp-port 25

    # Generate with org slug (auto-constructs recipient)
    python scripts/generate_test_email.py --org-slug acme \
        --from buyer@example.com --subject "PO 12345" \
        --attachment test.pdf

    # Multiple attachments
    python scripts/generate_test_email.py --to orders+acme@orderflow.local \
        --from buyer@example.com --subject "PO 12345" \
        --attachment order.pdf --attachment invoice.xlsx

    # Generate sample PDF attachment
    python scripts/generate_test_email.py --to orders+acme@orderflow.local \
        --from buyer@example.com --subject "PO 12345" \
        --generate-pdf order.pdf

SSOT Reference: spec 006-smtp-ingest, Task T041
"""

import argparse
import io
import mimetypes
import os
import smtplib
import sys
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional


def generate_sample_pdf(filename: str) -> bytes:
    """Generate a simple sample PDF for testing.

    Args:
        filename: Filename to use in PDF metadata

    Returns:
        bytes: PDF content
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        print(
            "ERROR: reportlab not installed. Install with: pip install reportlab",
            file=sys.stderr
        )
        sys.exit(1)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    # Add content
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 750, "PURCHASE ORDER")

    c.setFont("Helvetica", 12)
    c.drawString(100, 700, f"PO Number: PO-{filename[:10]}")
    c.drawString(100, 680, "Date: 2025-01-04")
    c.drawString(100, 660, "Vendor: ACME Wholesale Ltd.")

    c.drawString(100, 620, "Line Items:")
    c.drawString(120, 600, "1. Widget A - Qty: 100 - Price: $10.00")
    c.drawString(120, 580, "2. Widget B - Qty: 50 - Price: $15.00")
    c.drawString(120, 560, "3. Widget C - Qty: 75 - Price: $20.00")

    c.drawString(100, 520, "Total: $2,750.00")

    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer.read()


def generate_sample_csv(filename: str) -> bytes:
    """Generate a simple sample CSV for testing.

    Args:
        filename: Filename to use in CSV metadata

    Returns:
        bytes: CSV content
    """
    csv_content = """SKU,Description,Quantity,Unit Price,Total
WID-A-001,Widget A,100,10.00,1000.00
WID-B-002,Widget B,50,15.00,750.00
WID-C-003,Widget C,75,20.00,1500.00
"""
    return csv_content.encode('utf-8')


def generate_sample_excel(filename: str) -> bytes:
    """Generate a simple sample Excel file for testing.

    Args:
        filename: Filename to use in Excel metadata

    Returns:
        bytes: Excel content
    """
    try:
        from openpyxl import Workbook
    except ImportError:
        print(
            "ERROR: openpyxl not installed. Install with: pip install openpyxl",
            file=sys.stderr
        )
        sys.exit(1)

    wb = Workbook()
    ws = wb.active
    ws.title = "Purchase Order"

    # Add header
    ws.append(["PO Number", "PO-12345"])
    ws.append(["Date", "2025-01-04"])
    ws.append(["Vendor", "ACME Wholesale Ltd."])
    ws.append([])

    # Add line items
    ws.append(["SKU", "Description", "Quantity", "Unit Price", "Total"])
    ws.append(["WID-A-001", "Widget A", 100, 10.00, 1000.00])
    ws.append(["WID-B-002", "Widget B", 50, 15.00, 750.00])
    ws.append(["WID-C-003", "Widget C", 75, 20.00, 1500.00])
    ws.append([])
    ws.append(["", "", "", "Total:", 2750.00])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.read()


def create_email(
    from_email: str,
    to_email: str,
    subject: str,
    body: Optional[str] = None,
    attachments: Optional[List[str]] = None,
    generate_samples: Optional[List[str]] = None,
) -> MIMEMultipart:
    """Create MIME email message with attachments.

    Args:
        from_email: Sender email address
        to_email: Recipient email address
        subject: Email subject
        body: Email body text (optional)
        attachments: List of file paths to attach
        generate_samples: List of filenames to generate as samples

    Returns:
        MIMEMultipart: Email message
    """
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg['Message-ID'] = f"<test-{os.urandom(8).hex()}@orderflow-test>"

    # Add body
    if body is None:
        body = f"Please process the attached purchase order.\n\nPO: {subject}"

    msg.attach(MIMEText(body, 'plain'))

    # Attach files
    if attachments:
        for filepath in attachments:
            path = Path(filepath)
            if not path.exists():
                print(f"WARNING: Attachment not found: {filepath}", file=sys.stderr)
                continue

            # Detect MIME type
            mime_type, _ = mimetypes.guess_type(filepath)
            if mime_type is None:
                mime_type = 'application/octet-stream'

            maintype, subtype = mime_type.split('/', 1)

            # Read file
            with open(filepath, 'rb') as f:
                content = f.read()

            # Create attachment
            part = MIMEBase(maintype, subtype)
            part.set_payload(content)
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename="{path.name}"'
            )
            msg.attach(part)

            print(f"Attached: {path.name} ({len(content)} bytes)", file=sys.stderr)

    # Generate sample attachments
    if generate_samples:
        for filename in generate_samples:
            ext = Path(filename).suffix.lower()

            if ext == '.pdf':
                content = generate_sample_pdf(filename)
                mime_type = 'application/pdf'
            elif ext == '.csv':
                content = generate_sample_csv(filename)
                mime_type = 'text/csv'
            elif ext in ['.xlsx', '.xls']:
                content = generate_sample_excel(filename)
                mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            else:
                print(
                    f"ERROR: Unsupported file type for generation: {ext}",
                    file=sys.stderr
                )
                continue

            # Create attachment
            maintype, subtype = mime_type.split('/', 1)
            part = MIMEBase(maintype, subtype)
            part.set_payload(content)
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename="{filename}"'
            )
            msg.attach(part)

            print(
                f"Generated and attached: {filename} ({len(content)} bytes)",
                file=sys.stderr
            )

    return msg


def send_email(
    msg: MIMEMultipart,
    smtp_host: str = 'localhost',
    smtp_port: int = 25,
    smtp_user: Optional[str] = None,
    smtp_password: Optional[str] = None,
    use_tls: bool = False,
):
    """Send email via SMTP.

    Args:
        msg: Email message to send
        smtp_host: SMTP server hostname
        smtp_port: SMTP server port
        smtp_user: SMTP username (optional)
        smtp_password: SMTP password (optional)
        use_tls: Use STARTTLS (optional)
    """
    try:
        smtp = smtplib.SMTP(smtp_host, smtp_port)
        smtp.set_debuglevel(0)

        if use_tls:
            smtp.starttls()

        if smtp_user and smtp_password:
            smtp.login(smtp_user, smtp_password)

        smtp.send_message(msg)
        smtp.quit()

        print(
            f"Email sent successfully to {msg['To']} via {smtp_host}:{smtp_port}",
            file=sys.stderr
        )

    except Exception as e:
        print(f"ERROR sending email: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate test emails for OrderFlow SMTP ingest testing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Email metadata
    parser.add_argument(
        '--from',
        dest='from_email',
        required=True,
        help='Sender email address (e.g., buyer@example.com)'
    )
    parser.add_argument(
        '--to',
        dest='to_email',
        help='Recipient email address (e.g., orders+acme@orderflow.local)'
    )
    parser.add_argument(
        '--org-slug',
        help='Organization slug (auto-constructs recipient as orders+{slug}@orderflow.local)'
    )
    parser.add_argument(
        '--subject',
        default='Test Purchase Order',
        help='Email subject (default: "Test Purchase Order")'
    )
    parser.add_argument(
        '--body',
        help='Email body text (optional)'
    )

    # Attachments
    parser.add_argument(
        '--attachment',
        action='append',
        help='File to attach (can be specified multiple times)'
    )
    parser.add_argument(
        '--generate-pdf',
        metavar='FILENAME',
        help='Generate sample PDF attachment with given filename'
    )
    parser.add_argument(
        '--generate-csv',
        metavar='FILENAME',
        help='Generate sample CSV attachment with given filename'
    )
    parser.add_argument(
        '--generate-excel',
        metavar='FILENAME',
        help='Generate sample Excel attachment with given filename'
    )

    # SMTP sending
    parser.add_argument(
        '--send',
        action='store_true',
        help='Send email via SMTP (otherwise output to stdout)'
    )
    parser.add_argument(
        '--smtp-host',
        default='localhost',
        help='SMTP server hostname (default: localhost)'
    )
    parser.add_argument(
        '--smtp-port',
        type=int,
        default=25,
        help='SMTP server port (default: 25)'
    )
    parser.add_argument(
        '--smtp-user',
        help='SMTP username (optional)'
    )
    parser.add_argument(
        '--smtp-password',
        help='SMTP password (optional)'
    )
    parser.add_argument(
        '--smtp-tls',
        action='store_true',
        help='Use STARTTLS'
    )

    args = parser.parse_args()

    # Validate recipient
    if not args.to_email and not args.org_slug:
        parser.error("Either --to or --org-slug must be specified")

    # Construct recipient from org slug
    if args.org_slug:
        args.to_email = f"orders+{args.org_slug}@orderflow.local"

    # Collect sample generations
    generate_samples = []
    if args.generate_pdf:
        generate_samples.append(args.generate_pdf)
    if args.generate_csv:
        generate_samples.append(args.generate_csv)
    if args.generate_excel:
        generate_samples.append(args.generate_excel)

    # Create email
    msg = create_email(
        from_email=args.from_email,
        to_email=args.to_email,
        subject=args.subject,
        body=args.body,
        attachments=args.attachment,
        generate_samples=generate_samples if generate_samples else None,
    )

    # Send or output
    if args.send:
        send_email(
            msg,
            smtp_host=args.smtp_host,
            smtp_port=args.smtp_port,
            smtp_user=args.smtp_user,
            smtp_password=args.smtp_password,
            use_tls=args.smtp_tls,
        )
    else:
        # Output to stdout
        print(msg.as_string())


if __name__ == '__main__':
    main()
