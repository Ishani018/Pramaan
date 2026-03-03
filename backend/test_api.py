import httpx
import sys

def run():
    with open("mca_test_output2.txt", "rb") as f: # Just sending a dummy text file, type mismatch might trigger early fail but it hits endpoint!
        files = {'file_fy24': ('dummy.pdf', f, 'application/pdf')}
        data = {'site_visit_notes': 'Testing'}
        try:
            with httpx.Client() as client:
                res = client.post("http://localhost:8000/api/v1/analyze-report", files=files, data=data, timeout=30.0)
                print(res.status_code)
                print(res.text)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == '__main__':
    run()
