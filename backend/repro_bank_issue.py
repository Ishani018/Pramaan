from app.agents.deep_reader.bank_statement_analyzer import BankStatementAnalyzer

def test_user_format_repro():
    # Attempt to use various timestamp formats that might be in the user's file
    # Format 1: DD/MM/YYYY HH:MM:SS (Very common in India)
    # Format 2: YYYY-MM-DD HH:MM:SS
    content = """type,mode,amount,currentBalance,transactionTimestamp,txnId,narration
CREDIT,UPI,2500.50,12500.50,10/03/2024 10:30:00,TXN123,UPI/P2P/FRIEND
CREDIT,CARD,500.00,13000.50,11-03-2024 15:00:00,TXN124,STARBUCKS
"""
    analyzer = BankStatementAnalyzer()
    result = analyzer.analyze(content)
    print(f"Parsed Transactions: {result.total_transactions}")
    print(f"Total Credits: {result.total_credits}")
    
    if result.total_transactions == 0:
        print("\n❌ REPRODUCTION SUCCESSFUL: Rows skipped due to date parsing failure.")
    else:
        print("\n✅ REPRODUCTION FAILED: Rows parsed successfully.")

if __name__ == "__main__":
    test_user_format_repro()
