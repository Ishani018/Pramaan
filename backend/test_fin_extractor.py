from app.agents.deep_reader.financial_extractor import FinancialExtractor

def test_financial_extractor():
    texts = [
        "Revenue from operations for the year ended 31 March 2024 was 1,223.16 Cr.",
        "The Company reported total revenue of ₹ 435.7 Cr.",
        "Revenue from contracts with customers stood at 5,000.00 Cr in FY24.",
        "Revenue from operations 1,223.16 \n note particulars for the year rupees ₹"
    ]
    
    extractor = FinancialExtractor()
    for i, text in enumerate(texts):
        results = extractor.extract(text, "FY24")
        revenue = results.get("Revenue")
        if revenue:
            print(f"Test {i+1}: Found Revenue = {revenue['value']} Cr, Confidence = {revenue['confidence']}")
        else:
            print(f"Test {i+1}: Revenue NOT FOUND")

if __name__ == "__main__":
    test_financial_extractor()
