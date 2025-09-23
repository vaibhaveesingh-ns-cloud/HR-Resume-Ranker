#!/usr/bin/env python3
"""
Test script for GitHub link detection functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.gemini_service import GeminiService

def test_github_detection():
    """Test various GitHub link patterns in resume text"""
    
    # Initialize the service
    service = GeminiService()
    
    # Test cases with different GitHub link formats
    test_cases = [
        {
            "name": "Full HTTPS URL",
            "text": "Check out my projects at https://github.com/johndoe",
            "expected": ["https://github.com/johndoe"]
        },
        {
            "name": "HTTP URL (should convert to HTTPS)",
            "text": "My code is at http://github.com/janedoe/awesome-project",
            "expected": ["https://github.com/janedoe/awesome-project"]
        },
        {
            "name": "Domain without protocol",
            "text": "Visit github.com/developer123 for my repositories",
            "expected": ["https://github.com/developer123"]
        },
        {
            "name": "GitHub with colon format",
            "text": "GitHub: myusername",
            "expected": ["https://github.com/myusername"]
        },
        {
            "name": "At symbol format",
            "text": "@coder456 on GitHub",
            "expected": ["https://github.com/coder456"]
        },
        {
            "name": "GitHub profile format",
            "text": "GitHub Profile: awesome_dev",
            "expected": ["https://github.com/awesome_dev"]
        },
        {
            "name": "Contact section format",
            "text": "Contact Information:\n• Email: john@example.com\n• GitHub: john-developer\n• Phone: 123-456-7890",
            "expected": ["https://github.com/john-developer"]
        },
        {
            "name": "Project section format",
            "text": "Projects:\n1. Web App - Source Code: github.com/user/webapp\n2. Mobile App - Repository: https://github.com/user/mobile-app",
            "expected": ["https://github.com/user/webapp", "https://github.com/user/mobile-app"]
        },
        {
            "name": "Multiple formats in one text",
            "text": "I'm @developer on GitHub. Also check https://github.com/developer/project and my profile at github.com/developer",
            "expected": ["https://github.com/developer"]  # Should deduplicate
        },
        {
            "name": "Email-like format",
            "text": "Contact me at myusername@github.com for collaboration",
            "expected": ["https://github.com/myusername"]
        },
        {
            "name": "Bullet point format",
            "text": "Skills and Links:\n• Python, JavaScript\n• GitHub: tech-enthusiast\n• LinkedIn: /in/profile",
            "expected": ["https://github.com/tech-enthusiast"]
        },
        {
            "name": "Git abbreviation",
            "text": "Version Control: Git: my-username",
            "expected": ["https://github.com/my-username"]
        },
        {
            "name": "Invalid/Reserved usernames (should be filtered out)",
            "text": "Check out github.com/admin and github.com/api for more info",
            "expected": []  # These are reserved paths
        },
        {
            "name": "Invalid username format",
            "text": "My profile: github.com/-invalid-user and github.com/user--name",
            "expected": []  # Invalid username formats
        },
        {
            "name": "Mixed valid and invalid",
            "text": "Valid: github.com/valid-user123 Invalid: github.com/admin",
            "expected": ["https://github.com/valid-user123"]
        }
    ]
    
    print("🧪 Testing GitHub Link Detection")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        print(f"   Text: {test_case['text'][:100]}{'...' if len(test_case['text']) > 100 else ''}")
        
        try:
            # Extract GitHub links
            detected_links = service.extract_github_links(test_case['text'])
            expected_links = test_case['expected']
            
            print(f"   Expected: {expected_links}")
            print(f"   Detected: {detected_links}")
            
            # Check if results match (order doesn't matter)
            if set(detected_links) == set(expected_links):
                print("   ✅ PASSED")
                passed += 1
            else:
                print("   ❌ FAILED")
                failed += 1
                
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! GitHub detection is working correctly.")
    else:
        print(f"⚠️  {failed} test(s) failed. Please review the implementation.")
    
    return failed == 0

def test_url_validation():
    """Test GitHub URL validation"""
    print("\n🔍 Testing GitHub URL Validation")
    print("=" * 50)
    
    service = GeminiService()
    
    validation_tests = [
        ("https://github.com/validuser", True),
        ("https://github.com/valid-user123", True),
        ("https://github.com/user/repo", True),
        ("https://github.com/admin", False),  # Reserved
        ("https://github.com/api", False),    # Reserved
        ("https://github.com/-invalid", False),  # Starts with hyphen
        ("https://github.com/invalid-", False),  # Ends with hyphen
        ("https://github.com/user--name", False),  # Double hyphen
        ("http://github.com/user", False),    # HTTP not HTTPS
        ("https://gitlab.com/user", False),   # Wrong domain
        ("https://github.com/", False),       # No username
        ("not-a-url", False),                 # Invalid URL
    ]
    
    passed = 0
    failed = 0
    
    for url, expected in validation_tests:
        result = service.is_valid_github_url(url)
        status = "✅ PASSED" if result == expected else "❌ FAILED"
        print(f"   {url:<35} Expected: {expected:<5} Got: {result:<5} {status}")
        
        if result == expected:
            passed += 1
        else:
            failed += 1
    
    print(f"\n📊 Validation Results: {passed} passed, {failed} failed")
    return failed == 0

if __name__ == "__main__":
    print("🚀 Starting GitHub Detection Tests")
    
    # Set a dummy API key for testing (we won't actually call Gemini)
    os.environ['GEMINI_API_KEY'] = 'dummy-key-for-testing'
    
    try:
        detection_passed = test_github_detection()
        validation_passed = test_url_validation()
        
        if detection_passed and validation_passed:
            print("\n🎉 All tests completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed. Please review the implementation.")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 Test execution failed: {e}")
        sys.exit(1)
