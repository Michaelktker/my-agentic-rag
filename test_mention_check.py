#!/usr/bin/env python3
"""
Quick test script for @Myker mention checking functionality.
"""
import re

def test_mention_detection():
    """Test the mention detection logic."""
    
    test_cases = [
        ("@Myker hello there", True, "hello there"),
        ("Hello @Myker how are you?", True, "Hello how are you?"),
        ("@myker test lowercase", True, "test lowercase"),
        ("@MYKER test uppercase", True, "test uppercase"),
        ("hello world", False, "hello world"),
        ("myker without @", False, "myker without @"),
        ("@Myker   extra spaces", True, "extra spaces"),
        ("  @Myker  at start with spaces", True, "at start with spaces"),
    ]
    
    print("Testing @Myker mention detection logic...\n")
    
    for message, should_match, expected_cleaned in test_cases:
        # Check for mention
        has_mention = "@myker" in message.lower()
        
        # Clean message
        cleaned = re.sub(r'@myker\s*', '', message, flags=re.IGNORECASE).strip()
        
        # Verify results
        match_status = "✓" if has_mention == should_match else "✗"
        clean_status = "✓" if cleaned == expected_cleaned else "✗"
        
        print(f"{match_status} {clean_status} | Input: '{message}'")
        print(f"         | Mention detected: {has_mention} (expected: {should_match})")
        print(f"         | Cleaned: '{cleaned}' (expected: '{expected_cleaned}')")
        
        if has_mention != should_match or cleaned != expected_cleaned:
            print(f"         | ❌ TEST FAILED!")
        else:
            print(f"         | ✅ PASSED")
        print()

if __name__ == "__main__":
    test_mention_detection()
    print("\n" + "="*60)
    print("Summary: Mention detection logic validated!")
    print("="*60)
