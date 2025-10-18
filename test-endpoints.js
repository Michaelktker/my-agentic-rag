#!/usr/bin/env node

// Test script for dual endpoint functionality
const axios = require('axios');

// Configuration
const PRODUCTION_ADK_URL = process.env.PRODUCTION_ADK_URL || 'https://my-agentic-rag-production.us-central1.run.app';
const STAGING_ADK_URL = process.env.STAGING_ADK_URL || 'https://my-agentic-rag-454188184539.us-central1.run.app';
const HEALTH_CHECK_TIMEOUT = parseInt(process.env.HEALTH_CHECK_TIMEOUT || '3000');

console.log('🧪 Testing Dual Endpoint Configuration');
console.log('=====================================');
console.log(`📍 Production URL: ${PRODUCTION_ADK_URL}`);
console.log(`📍 Staging URL: ${STAGING_ADK_URL}`);
console.log(`⏱️ Timeout: ${HEALTH_CHECK_TIMEOUT}ms`);
console.log('');

/**
 * Health check function for ADK endpoints
 */
async function checkEndpointHealth(url, timeout = HEALTH_CHECK_TIMEOUT) {
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);
        
        // Try health endpoint first
        const healthUrl = `${url.replace(/\/$/, '')}/health`;
        console.log(`🔍 Checking health endpoint: ${healthUrl}`);
        
        const response = await fetch(healthUrl, { 
            signal: controller.signal,
            method: 'GET'
        });
        
        clearTimeout(timeoutId);
        
        if (response.ok) {
            const data = await response.json();
            console.log(`✅ Health check passed for ${url}`);
            console.log(`   Status: ${response.status}`);
            console.log(`   Response: ${JSON.stringify(data, null, 2)}`);
            return true;
        }
        
        console.log(`❌ Health check failed for ${url}: ${response.status}`);
        return false;
        
    } catch (error) {
        console.log(`❌ Health check failed for ${url}: ${error.message}`);
        return false;
    }
}

/**
 * Get active ADK endpoint with fallback logic
 */
async function getActiveAdkEndpoint() {
    console.log('\n🔍 Determining active ADK endpoint...');
    
    // Try production first
    console.log('📡 Testing production endpoint...');
    if (await checkEndpointHealth(PRODUCTION_ADK_URL)) {
        console.log(`✅ Using production endpoint: ${PRODUCTION_ADK_URL}`);
        return PRODUCTION_ADK_URL;
    }
    
    // Fallback to staging
    console.log('\n⚠️ Production unavailable, trying staging...');
    if (await checkEndpointHealth(STAGING_ADK_URL)) {
        console.log(`✅ Using staging endpoint: ${STAGING_ADK_URL}`);
        return STAGING_ADK_URL;
    }
    
    // Both down - use production and let error bubble up
    console.log('\n❌ Both endpoints unavailable, defaulting to production');
    return PRODUCTION_ADK_URL;
}

/**
 * Test a simple API call to the selected endpoint
 */
async function testApiCall(endpoint) {
    try {
        console.log(`\n🧪 Testing API call to: ${endpoint}`);
        
        const payload = {
            appName: "app",
            userId: "test_user_dual_endpoint",
            sessionId: "test_session_" + Date.now(),
            newMessage: {
                parts: [{
                    text: "Hello, this is a test from the dual endpoint system!"
                }],
                role: "user"
            },
            streaming: false
        };
        
        console.log(`📤 Sending test payload...`);
        
        const response = await axios.post(`${endpoint}/run`, payload, {
            headers: { 'Content-Type': 'application/json' },
            timeout: 30000
        });
        
        console.log(`✅ API call successful!`);
        console.log(`   Status: ${response.status}`);
        console.log(`   Response preview: ${JSON.stringify(response.data).substring(0, 200)}...`);
        
        return true;
        
    } catch (error) {
        console.log(`❌ API call failed: ${error.message}`);
        if (error.response) {
            console.log(`   Status: ${error.response.status}`);
            console.log(`   Data: ${JSON.stringify(error.response.data)}`);
        }
        return false;
    }
}

/**
 * Main test function
 */
async function runTests() {
    try {
        console.log('🚀 Starting endpoint tests...\n');
        
        // Test endpoint selection
        const activeEndpoint = await getActiveAdkEndpoint();
        
        // Test API call to selected endpoint
        await testApiCall(activeEndpoint);
        
        console.log('\n🎉 Endpoint testing completed!');
        console.log('=====================================');
        
    } catch (error) {
        console.error('💥 Test failed:', error.message);
        process.exit(1);
    }
}

// Run the tests
if (require.main === module) {
    runTests();
}

module.exports = { checkEndpointHealth, getActiveAdkEndpoint, testApiCall };