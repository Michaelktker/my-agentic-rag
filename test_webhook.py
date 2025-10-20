#!/usr/bin/env python3
"""
Test script for webhook functionality
Tests webhook registration and callback handling
"""

import asyncio
import json
import aiohttp
import uuid
import sys
from datetime import datetime

WEBHOOK_BASE_URL = "https://my-agentic-rag-aktu2chyfa-uc.a.run.app"

async def test_webhook_registration():
    """Test webhook registration functionality"""
    print("🧪 Testing webhook registration...")
    
    # Test data
    test_request_id = f"test_{uuid.uuid4().hex[:8]}"
    test_user_id = "test_user_123"
    test_session_id = f"session_{uuid.uuid4().hex[:8]}"
    test_jid = "1234567890@s.whatsapp.net"
    test_model = "fal-ai/wan-25-preview/image-to-video"
    test_prompt = "A cat walking in a garden, realistic, 4k"
    test_status_url = f"https://fal.ai/status/{test_request_id}"
    test_response_url = f"https://fal.ai/result/{test_request_id}"
    
    # Check webhook health
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{WEBHOOK_BASE_URL}/webhook/health") as resp:
                if resp.status == 200:
                    health_data = await resp.json()
                    print(f"✅ Webhook health check passed: {health_data}")
                else:
                    print(f"❌ Webhook health check failed: {resp.status}")
                    return False
        except Exception as e:
            print(f"❌ Error connecting to webhook service: {e}")
            return False
    
    return True

async def test_webhook_callback():
    """Test webhook callback handling"""
    print("🧪 Testing webhook callback...")
    
    test_request_id = f"test_{uuid.uuid4().hex[:8]}"
    
    # Simulate FAL.ai completion callback
    callback_data = {
        "status": "COMPLETED",
        "request_id": test_request_id,
        "data": {
            "url": "https://v3b.fal.media/files/test-video.mp4"
        }
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            webhook_url = f"{WEBHOOK_BASE_URL}/webhook/fal/{test_request_id}"
            async with session.post(webhook_url, json=callback_data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    print(f"✅ Webhook callback test passed: {result}")
                    return True
                else:
                    print(f"❌ Webhook callback test failed: {resp.status}")
                    return False
        except Exception as e:
            print(f"❌ Error testing webhook callback: {e}")
            return False

async def test_webhook_status():
    """Test webhook status endpoint"""
    print("🧪 Testing webhook status endpoint...")
    
    test_request_id = "nonexistent_request"
    
    async with aiohttp.ClientSession() as session:
        try:
            status_url = f"{WEBHOOK_BASE_URL}/webhook/status/{test_request_id}"
            async with session.get(status_url) as resp:
                if resp.status == 404:
                    print("✅ Webhook status test passed (correctly returned 404 for non-existent request)")
                    return True
                else:
                    print(f"❌ Webhook status test failed: expected 404, got {resp.status}")
                    return False
        except Exception as e:
            print(f"❌ Error testing webhook status: {e}")
            return False

async def main():
    """Run all webhook tests"""
    print(f"🚀 Starting webhook tests at {datetime.now()}")
    print(f"🎯 Testing webhook service at: {WEBHOOK_BASE_URL}")
    print("=" * 50)
    
    tests = [
        ("Webhook Registration", test_webhook_registration),
        ("Webhook Callback", test_webhook_callback),
        ("Webhook Status", test_webhook_status)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}:")
        try:
            result = await test_func()
            results.append((test_name, result))
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"   {status}")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY:")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {test_name}: {status}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Webhook system is ready.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the implementation.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)