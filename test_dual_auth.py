#!/usr/bin/env python3
"""
Test script for dual authentication (Clerk + Discord OAuth)
Tests the @dual_auth_required decorator with both token types.
"""

import os
import sys
import requests
from datetime import datetime

# Configuration
API_BASE_URL = os.environ.get("API_URL", "http://localhost:8000")
CLERK_TOKEN = os.environ.get("CLERK_TEST_TOKEN", "")
DISCORD_TOKEN = os.environ.get("DISCORD_TEST_TOKEN", "")
ORG_PREFIX = "soda"  # Change if needed

def print_test_header(test_name):
    """Print formatted test header"""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")

def print_result(passed, message):
    """Print test result"""
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"{status}: {message}")

def test_no_auth():
    """Test that endpoints reject requests with no authentication"""
    print_test_header("No Authentication (Should Fail)")
    
    url = f"{API_BASE_URL}/api/storefront/{ORG_PREFIX}/orders"
    
    try:
        response = requests.get(url, timeout=5)
        
        if response.status_code == 401:
            print_result(True, "Correctly rejected request with no auth")
            print(f"Response: {response.json()}")
            return True
        else:
            print_result(False, f"Expected 401, got {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print_result(False, f"Request failed: {e}")
        return False

def test_clerk_auth():
    """Test Clerk token authentication"""
    print_test_header("Clerk Token Authentication")
    
    if not CLERK_TOKEN:
        print_result(False, "No CLERK_TEST_TOKEN provided in environment")
        print("Set CLERK_TEST_TOKEN environment variable to test Clerk auth")
        return False
    
    url = f"{API_BASE_URL}/api/storefront/{ORG_PREFIX}/orders"
    headers = {"Authorization": f"Bearer {CLERK_TOKEN}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code in [200, 403, 404]:
            # 200 = success, 403 = authorized but insufficient permissions, 404 = org not found
            # All these indicate the token was accepted
            print_result(True, f"Clerk token accepted (status: {response.status_code})")
            if response.status_code == 200:
                data = response.json()
                print(f"Response: Retrieved {len(data)} orders")
            else:
                print(f"Response: {response.json()}")
            return True
        elif response.status_code == 401:
            print_result(False, "Clerk token was rejected")
            print(f"Response: {response.json()}")
            return False
        else:
            print_result(False, f"Unexpected status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print_result(False, f"Request failed: {e}")
        return False

def test_discord_oauth():
    """Test Discord OAuth token authentication"""
    print_test_header("Discord OAuth Token Authentication")
    
    if not DISCORD_TOKEN:
        print_result(False, "No DISCORD_TEST_TOKEN provided in environment")
        print("Set DISCORD_TEST_TOKEN environment variable to test Discord OAuth")
        return False
    
    url = f"{API_BASE_URL}/api/storefront/{ORG_PREFIX}/orders"
    headers = {"Authorization": f"Bearer {DISCORD_TOKEN}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code in [200, 403, 404]:
            # 200 = success, 403 = authorized but insufficient permissions, 404 = org not found
            print_result(True, f"Discord OAuth token accepted (status: {response.status_code})")
            if response.status_code == 200:
                data = response.json()
                print(f"Response: Retrieved {len(data)} orders")
            else:
                print(f"Response: {response.json()}")
            return True
        elif response.status_code == 401:
            print_result(False, "Discord OAuth token was rejected")
            print(f"Response: {response.json()}")
            return False
        else:
            print_result(False, f"Unexpected status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print_result(False, f"Request failed: {e}")
        return False

def test_invalid_token():
    """Test that invalid tokens are rejected"""
    print_test_header("Invalid Token (Should Fail)")
    
    url = f"{API_BASE_URL}/api/storefront/{ORG_PREFIX}/orders"
    headers = {"Authorization": "Bearer invalid_token_12345"}
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 401:
            print_result(True, "Correctly rejected invalid token")
            print(f"Response: {response.json()}")
            return True
        else:
            print_result(False, f"Expected 401, got {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print_result(False, f"Request failed: {e}")
        return False

def test_wallet_endpoint_clerk():
    """Test wallet endpoint with Clerk auth (requires email match)"""
    print_test_header("Wallet Endpoint with Clerk Token")
    
    if not CLERK_TOKEN:
        print_result(False, "No CLERK_TEST_TOKEN provided")
        return False
    
    # Try with a test email
    test_email = "test@example.com"
    url = f"{API_BASE_URL}/api/storefront/{ORG_PREFIX}/wallet/{test_email}"
    headers = {"Authorization": f"Bearer {CLERK_TOKEN}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        
        # We expect either 200 (success), 403 (email mismatch), or 404 (user/org not found)
        if response.status_code in [200, 403, 404]:
            print_result(True, f"Wallet endpoint accepted Clerk token (status: {response.status_code})")
            print(f"Response: {response.json()}")
            return True
        elif response.status_code == 401:
            print_result(False, "Clerk token was rejected")
            print(f"Response: {response.json()}")
            return False
        else:
            print_result(False, f"Unexpected status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print_result(False, f"Request failed: {e}")
        return False

def test_health_check():
    """Test that API is responding"""
    print_test_header("API Health Check")
    
    url = f"{API_BASE_URL}/health"
    
    try:
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            print_result(True, "API is healthy and responding")
            return True
        else:
            print_result(False, f"Health check returned {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print_result(False, f"Cannot connect to API: {e}")
        return False

def main():
    """Run all tests"""
    print(f"\n{'#'*60}")
    print(f"# DUAL AUTHENTICATION TEST SUITE")
    print(f"# API: {API_BASE_URL}")
    print(f"# Time: {datetime.now().isoformat()}")
    print(f"{'#'*60}")
    
    results = []
    
    # Run tests
    results.append(("Health Check", test_health_check()))
    results.append(("No Auth", test_no_auth()))
    results.append(("Invalid Token", test_invalid_token()))
    results.append(("Clerk Auth", test_clerk_auth()))
    results.append(("Discord OAuth", test_discord_oauth()))
    results.append(("Wallet (Clerk)", test_wallet_endpoint_clerk()))
    
    # Print summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓" if result else "✗"
        print(f"{status} {test_name}")
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
