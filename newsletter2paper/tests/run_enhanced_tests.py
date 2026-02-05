#!/usr/bin/env python3
"""Test runner for all RSS service enhancements."""

import unittest
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def run_enhanced_rss_tests():
    """Run all enhanced RSS service tests."""
    
    # Discover and run tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add our new test files
    test_modules = [
        'tests.test_rss_service_enhanced',
        'tests.test_rss_service_content', 
        'tests.test_articles_router'
    ]
    
    for module in test_modules:
        try:
            suite.addTests(loader.loadTestsFromName(module))
            print(f"✓ Loaded tests from {module}")
        except Exception as e:
            print(f"✗ Failed to load tests from {module}: {e}")
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.failures:
        print(f"\nFAILURES ({len(result.failures)}):")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback.split(chr(10))[-2]}")
    
    if result.errors:
        print(f"\nERRORS ({len(result.errors)}):")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback.split(chr(10))[-2]}")
    
    # Return success status
    return len(result.failures) == 0 and len(result.errors) == 0


def run_specific_test_class(test_class_name):
    """Run a specific test class."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Map test class names to modules
    test_class_map = {
        'TestEnhancedFeedDiscovery': 'tests.test_rss_service_enhanced',
        'TestRSSParsingUtilities': 'tests.test_rss_service_enhanced', 
        'TestDateFilteringUtilities': 'tests.test_rss_service_enhanced',
        'TestEnhancedContentExtraction': 'tests.test_rss_service_content',
        'TestUtilityMethods': 'tests.test_rss_service_content',
        'TestIssueArticleFetching': 'tests.test_rss_service_content',
        'TestArticlesRouter': 'tests.test_articles_router',
        'TestArticlesRouterIntegration': 'tests.test_articles_router'
    }
    
    if test_class_name in test_class_map:
        module_name = test_class_map[test_class_name]
        try:
            suite.addTests(loader.loadTestsFromName(f'{module_name}.{test_class_name}'))
            print(f"✓ Loaded {test_class_name} from {module_name}")
        except Exception as e:
            print(f"✗ Failed to load {test_class_name}: {e}")
            return False
    else:
        print(f"✗ Unknown test class: {test_class_name}")
        print(f"Available test classes: {list(test_class_map.keys())}")
        return False
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return len(result.failures) == 0 and len(result.errors) == 0


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Run specific test class
        test_class = sys.argv[1]
        success = run_specific_test_class(test_class)
    else:
        # Run all enhanced RSS tests
        success = run_enhanced_rss_tests()
    
    sys.exit(0 if success else 1)