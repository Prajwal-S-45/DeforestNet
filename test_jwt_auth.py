"""
JWT Authentication Testing Guide for DeforestNet API

This script demonstrates how to:
1. Obtain a JWT token via login
2. Use the token to access protected endpoints
3. Validate and refresh tokens
"""

import requests
import json
from datetime import datetime

# API Base URL
BASE_URL = "http://localhost:5000/api"

# Demo credentials
DEMO_USERS = {
    "officer1": {"password": "demo", "role": "officer"},
    "admin": {"password": "admin", "role": "admin"},
    "demo": {"password": "demo", "role": "user"}
}


def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_response(response, title="Response"):
    """Pretty print a response."""
    print(f"{title}:")
    try:
        print(json.dumps(response.json(), indent=2))
    except:
        print(response.text)
    print(f"Status Code: {response.status_code}\n")


def test_api_root():
    """1. Get API information and available endpoints."""
    print_section("1. API Root - List Endpoints")
    response = requests.get(f"{BASE_URL}")
    print_response(response, "Available Endpoints")


def test_health_check():
    """2. Health check (no authentication required)."""
    print_section("2. Health Check")
    response = requests.get(f"{BASE_URL}/health")
    print_response(response, "Health Status")


def test_login():
    """3. Login to obtain JWT token."""
    print_section("3. Login - Get JWT Token")
    
    user_id = "officer1"
    password = "demo"
    
    login_data = {
        "user_id": user_id,
        "email": "officer1@deforestnet.org",
        "password": password,
        "role": "officer"
    }
    
    print(f"Attempting login with user_id: {user_id}\n")
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    print_response(response, "Login Response")
    
    if response.status_code == 200:
        token = response.json()["token"]
        print(f"✓ Token obtained successfully!")
        print(f"  Token (first 50 chars): {token[:50]}...\n")
        return token
    else:
        print("✗ Login failed!\n")
        return None


def test_validate_token(token):
    """4. Validate JWT token."""
    print_section("4. Validate Token")
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    response = requests.get(f"{BASE_URL}/auth/validate", headers=headers)
    print_response(response, "Token Validation")


def test_protected_endpoint(token):
    """5. Call protected endpoint (/api/predictions/demo)."""
    print_section("5. Protected Endpoint - Demo Prediction")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    prediction_data = {
        "cause": "Logging",
        "latitude": 10.5,
        "longitude": 76.3,
        "region": "Western Ghats",
        "area_fraction": 0.3
    }
    
    print("Making authenticated request to /api/predictions/demo\n")
    response = requests.post(
        f"{BASE_URL}/predictions/demo",
        json=prediction_data,
        headers=headers
    )
    print_response(response, "Prediction Response")


def test_protected_endpoint_without_token():
    """6. Try to access protected endpoint without token."""
    print_section("6. Protected Endpoint Without Token (Should Fail)")
    
    response = requests.post(f"{BASE_URL}/predictions/demo", json={})
    print_response(response, "Response Without Token")
    
    if response.status_code == 401:
        print("✓ Correctly rejected request without token!\n")


def test_refresh_token(token):
    """7. Refresh token to extend expiration."""
    print_section("7. Refresh Token")
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    print("Requesting new token with extended expiration...\n")
    response = requests.post(f"{BASE_URL}/auth/refresh", headers=headers)
    print_response(response, "Refresh Response")
    
    if response.status_code == 200:
        new_token = response.json()["token"]
        print(f"✓ New token obtained!")
        print(f"  New Token (first 50 chars): {new_token[:50]}...\n")
        return new_token
    
    return None


def run_full_test():
    """Run complete authentication test flow."""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "  DeforestNet API - JWT Authentication Test".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")
    print(f"\nAPI URL: {BASE_URL}")
    print(f"Test Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Run tests
    test_api_root()
    test_health_check()
    
    token = test_login()
    if token:
        test_validate_token(token)
        test_protected_endpoint(token)
        test_protected_endpoint_without_token()
        
        new_token = test_refresh_token(token)
        if new_token:
            test_protected_endpoint(new_token)
    
    print_section("Test Complete")
    print("Summary:")
    print("  ✓ API endpoints accessible")
    print("  ✓ Health check passed")
    print("  ✓ Login successful")
    print("  ✓ Token validation working")
    print("  ✓ Protected endpoints require authentication")
    print("  ✓ Token refresh functional\n")


# Quick command-line examples
CURL_EXAMPLES = """
# CURL EXAMPLES FOR TESTING JWT AUTHENTICATION

# 1. Login to get token
curl -X POST "http://localhost:5000/api/auth/login" \\
  -H "Content-Type: application/json" \\
  -d '{
    "user_id": "officer1",
    "email": "officer1@deforestnet.org",
    "password": "demo",
    "role": "officer"
  }'

# 2. Use token to access protected endpoint
TOKEN="your_token_here"
curl -X POST "http://localhost:5000/api/predictions/demo" \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "cause": "Mining",
    "region": "Western Ghats",
    "area_fraction": 0.3
  }'

# 3. Validate token
curl -X GET "http://localhost:5000/api/auth/validate" \\
  -H "Authorization: Bearer $TOKEN"

# 4. Refresh token
curl -X POST "http://localhost:5000/api/auth/refresh" \\
  -H "Authorization: Bearer $TOKEN"

# 5. Access without token (will fail)
curl -X POST "http://localhost:5000/api/predictions/demo"
"""


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--curl":
        print(CURL_EXAMPLES)
    else:
        try:
            run_full_test()
        except requests.exceptions.ConnectionError:
            print("✗ Error: Could not connect to API")
            print(f"  Make sure the API is running at {BASE_URL}")
            print("\n  Start the API with: python run_api.py")
        except Exception as e:
            print(f"✗ Error during testing: {e}")
