import sys
import io
from pathlib import Path
from fastapi.testclient import TestClient

# Add backend to path
sys.path.append(str(Path(__file__).parent / "backend"))

# Import the main FastAPI app, not just the router function
from main import app 

client = TestClient(app)

def test():
    print("Testing backend analysis pipeline via TestClient...")
    
    # Create a dummy PDF upload file
    pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    
    # Format it as a multipart/form-data payload. 
    # Note the key "file_fy24" to match your frontend/backend logic.
    files = {
        "file_fy24": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")
    }
    
    try:
        # Use the test client to POST to the endpoint
        response = client.post("/api/v1/analyze-report", files=files)
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("Success!")
            print(response.json())
        else:
            print(f"Failed: {response.text}")
            
    except Exception as e:
        import traceback
        print("Encountered an exception:")
        traceback.print_exc()

if __name__ == "__main__":
    # TestClient is synchronous, so we don't need asyncio.run()
    test()
