#!/usr/bin/env python3
"""
Debug script for GitHub link detection
"""

import sys
import os
import re
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.gemini_service import GeminiService

def debug_specific_cases():
    """Debug the failing test cases"""
    
    os.environ['GEMINI_API_KEY'] = 'dummy-key-for-testing'
    service = GeminiService()
    
    failing_cases = [
        {
            "name": "GitHub profile format",
            "text": "GitHub Profile: awesome_dev",
            "expected": ["https://github.com/awesome_dev"]
        },
        {
            "name": "Project section format",
            "text": "Projects:\n1. Web App - Source Code: github.com/user/webapp\n2. Mobile App - Repository: https://github.com/user/mobile-app",
            "expected": ["https://github.com/user/webapp", "https://github.com/user/mobile-app"]
        },
        {
            "name": "Multiple formats in one text",
            "text": "I'm @developer on GitHub. Also check https://github.com/developer/project and my profile at github.com/developer",
            "expected": ["https://github.com/developer"]
        }
    ]
    
    for case in failing_cases:
        print(f"\n=== Debugging: {case['name']} ===")
        print(f"Text: {repr(case['text'])}")
        print(f"Expected: {case['expected']}")
        
        # Clean text
        text_clean = case['text'].replace('\n', ' ').replace('\t', ' ')
        print(f"Cleaned text: {repr(text_clean)}")
        
        # Test individual patterns
        patterns = [
            ("Full HTTPS URLs", r'https?://github\.com/[a-zA-Z0-9._-]+(?:/[a-zA-Z0-9._/-]*)?'),
            ("Domain without protocol", r'(?:www\.)?github\.com/[a-zA-Z0-9._-]+(?:/[a-zA-Z0-9._/-]*)?'),
            ("GitHub Profile pattern", r'github\s+(?:profile|account|handle)\s*:\s*([a-zA-Z0-9._-]+)'),
            ("@username on GitHub", r'@([a-zA-Z0-9._-]+)\s*(?:\(?\s*(?:on\s+)?github\s*\)?)')
        ]
        
        for pattern_name, pattern in patterns:
            matches = re.findall(pattern, text_clean, re.IGNORECASE)
            if matches:
                print(f"  {pattern_name}: {matches}")
        
        # Get actual result
        result = service.extract_github_links(case['text'])
        print(f"Actual result: {result}")
        print("-" * 50)

if __name__ == "__main__":
    debug_specific_cases()
