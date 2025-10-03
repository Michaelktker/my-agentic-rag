#!/usr/bin/env python3
"""
Simple test script to verify that the GitHub MCP integration is working correctly.
"""
import os
import sys
import asyncio

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agent import root_agent

async def test_github_mcp_integration():
    """Test that the GitHub MCP integration is properly configured."""
    
    # Check if GITHUB_PAT is set
    github_pat = os.environ.get("GITHUB_PAT")
    if not github_pat:
        print("❌ GITHUB_PAT environment variable is not set.")
        print("   Please run: export GITHUB_PAT='your_token_here'")
        return False
    
    # Check if the agent has the expected tools
    tools = root_agent.tools if hasattr(root_agent, 'tools') else []
    
    print(f"📋 Agent has {len(tools)} tools configured:")
    for i, tool in enumerate(tools):
        tool_name = getattr(tool, 'name', str(type(tool).__name__))
        print(f"   {i+1}. {tool_name}")
    
    # Check if GitHub MCP tools are available
    has_github_mcp = any('MCP' in str(type(tool).__name__) for tool in tools)
    
    if has_github_mcp:
        print("✅ GitHub MCP integration is properly configured!")
        print("   Your agent can now interact with GitHub repositories.")
        return True
    else:
        print("⚠️  GitHub MCP tools may not be loaded.")
        print("   This could be due to:")
        print("   - Missing GITHUB_PAT environment variable")
        print("   - Docker not running")
        print("   - Network connectivity issues")
        return False

def main():
    """Main function to run the test."""
    print("🧪 Testing GitHub MCP Integration for ADK Agent...")
    print()
    
    try:
        # Check if GITHUB_PAT is set
        if not os.environ.get("GITHUB_PAT"):
            print("❌ GITHUB_PAT environment variable not set")
            return False
        
        success = asyncio.run(test_github_mcp_integration())
        
        print()
        if success:
            print("🎉 Test passed! Your agent is ready to use GitHub tools.")
            print()
            print("Try running 'make playground' and asking questions like:")
            print("  - 'Search for Python repositories on GitHub'")
            print("  - 'Get information about my repository'")
            print("  - 'Show me recent issues in a specific repository'")
        else:
            print("❌ Test failed. Please check the setup and try again.")
            return 1
            
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())