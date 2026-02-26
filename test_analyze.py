import sys
import asyncio
from pathlib import Path
from fastapi import UploadFile
import io

# Add backend to path
sys.path.append(str(Path(__file__).parent / "backend"))

from app.api.v1.analyze_report import analyze_report

async def test():
    print("Testing backend analysis pipeline directly...")
    # create a dummy pdf upload file
    pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    file = UploadFile(filename="test.pdf", file=io.BytesIO(pdf_content))
    try:
        res = await analyze_report([file])
        print("Success!")
    except Exception as e:
        import traceback
        print("Encountered 500 equivalent error:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
