"""Print an HTML file to PDF with headless Edge (or Chrome) and rewrite it with empty metadata."""
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from pypdf import PdfReader, PdfWriter


def find_browser() -> str:
    for c in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              shutil.which("msedge") or "", shutil.which("google-chrome") or "", shutil.which("chromium") or ""]:
        if c and Path(c).exists():
            return c
    raise FileNotFoundError("Edge or Chrome is needed to print the PDF")


def print_pdf(html: Path, pdf: Path, title: str) -> Path:
    tmp = pdf.with_name("_print.pdf")
    if tmp.exists():
        tmp.unlink()
    profile = tempfile.mkdtemp()            # own profile: an open Edge window would otherwise take the call
    subprocess.run([find_browser(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={profile}",
                    "--run-all-compositor-stages-before-draw", "--virtual-time-budget=8000",
                    f"--print-to-pdf={tmp}", html.resolve().as_uri()], check=True, timeout=180,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    last = -1
    for _ in range(120):                    # Edge can return before its child process has written the file
        time.sleep(1)
        size = tmp.stat().st_size if tmp.exists() else -1
        if size > 0 and size == last:
            break
        last = size
    shutil.rmtree(profile, ignore_errors=True)
    reader, writer = PdfReader(str(tmp)), PdfWriter()
    for pg in reader.pages:
        writer.add_page(pg)
    writer.add_metadata({"/Title": title, "/Author": "", "/Creator": "", "/Producer": "", "/Subject": "", "/Keywords": ""})
    with open(pdf, "wb") as fh:
        writer.write(fh)
    tmp.unlink()
    return pdf
