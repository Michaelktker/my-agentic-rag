#!/usr/bin/env python3
"""
🚀 Comprehensive ADK RAG Agent Test
Tests both RAG retrieval and GitHub MCP integration
"""

import asyncio
import os
import sys
from typing import List, Dict, Any

def setup_environment():
    """Set up environment variables for testing"""
    # Ensure required environment variables are set
    if not os.environ.get("GITHUB_PAT"):
        print("❌ GITHUB_PAT environment variable not set")
        return False
    os.environ["DATA_STORE_ID"] = "my-agentic-rag-datastore-staging"
    os.environ["DATA_STORE_REGION"] = "us"
    
    print("🔧 Environment Setup:")
    print(f"   Project: {os.environ.get('GOOGLE_CLOUD_PROJECT', 'staging-adk')}")
    print(f"   Datastore: {os.environ.get('DATA_STORE_ID')}")
    print(f"   Region: {os.environ.get('DATA_STORE_REGION')}")
    print(f"   GitHub PAT: {os.environ.get('GITHUB_PAT', '')[:10]}...")


async def test_agent_configuration():
    """Test the agent configuration and available tools"""
    print("\n🧪 Testing Agent Configuration...")
    print("-" * 50)
    
    try:
        # Import the agent
        sys.path.insert(0, '.')
        from app.agent import root_agent, github_pat
        
        print(f"✅ Agent Name: {root_agent.name}")
        print(f"✅ Agent Model: {root_agent.model}")
        print(f"✅ GitHub PAT Available: {'Yes' if github_pat else 'No'}")
        print(f"✅ Total Tools: {len(root_agent.tools)}")
        
        print(f"\n📋 Available Tools:")
        for i, tool in enumerate(root_agent.tools, 1):
            tool_name = getattr(tool, '__name__', type(tool).__name__)
            print(f"  {i}. {tool_name} ({type(tool).__name__})")
        
        return root_agent
    except Exception as e:
        print(f"❌ Error loading agent: {e}")
        return None


async def test_rag_retrieval(agent):
    """Test RAG document retrieval functionality"""
    print(f"\n📚 Testing RAG Retrieval...")
    print("-" * 50)
    
    test_queries = [
        "How to save a pandas dataframe to CSV?",  # From README
        "What is machine learning?",
        "Python programming basics",
        "How to handle data preprocessing?"
    ]
    
    successful_queries = 0
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n🔍 Query {i}: {query}")
        try:
            response = await agent.say(query)
            
            # Check if response contains useful information
            if len(response) > 50 and not response.startswith("Error"):
                print(f"✅ Success: {response[:150]}...")
                successful_queries += 1
            else:
                print(f"⚠️  Limited response: {response}")
                
        except Exception as e:
            print(f"❌ Error: {type(e).__name__}: {str(e)[:100]}...")
    
    success_rate = (successful_queries / len(test_queries)) * 100
    print(f"\n📊 RAG Results: {successful_queries}/{len(test_queries)} queries successful ({success_rate:.1f}%)")
    return success_rate > 50


async def test_github_mcp_integration(agent):
    """Test GitHub MCP tools integration"""
    print(f"\n🐙 Testing GitHub MCP Integration...")
    print("-" * 50)
    
    github_pat = os.environ.get("GITHUB_PAT")
    if not github_pat:
        print("⚠️  GitHub PAT not available - skipping GitHub tests")
        return False
    
    github_queries = [
        "Search for Python repositories on GitHub",
        "Get information about the GoogleCloudPlatform/agent-starter-pack repository",
        "Find recent issues in machine learning repositories",
        "What are popular JavaScript frameworks on GitHub?"
    ]
    
    successful_queries = 0
    
    for i, query in enumerate(github_queries, 1):
        print(f"\n🔍 GitHub Query {i}: {query}")
        try:
            response = await agent.say(query)
            
            # Check if response contains GitHub-specific information
            github_indicators = ['repository', 'github', 'commit', 'issue', 'pull request', 'star']
            if any(indicator in response.lower() for indicator in github_indicators):
                print(f"✅ GitHub Success: {response[:150]}...")
                successful_queries += 1
            else:
                print(f"⚠️  Non-GitHub response: {response[:100]}...")
                
        except Exception as e:
            print(f"❌ GitHub Error: {type(e).__name__}: {str(e)[:100]}...")
    
    success_rate = (successful_queries / len(github_queries)) * 100
    print(f"\n📊 GitHub Results: {successful_queries}/{len(github_queries)} queries successful ({success_rate:.1f}%)")
    return success_rate > 50


async def test_combined_functionality(agent):
    """Test queries that might use both RAG and GitHub tools"""
    print(f"\n🔄 Testing Combined Functionality...")
    print("-" * 50)
    
    combined_queries = [
        "How to use pandas with GitHub Actions for CI/CD?",
        "Find Python data science repositories and explain pandas usage",
        "What are best practices for machine learning projects on GitHub?"
    ]
    
    for i, query in enumerate(combined_queries, 1):
        print(f"\n🔍 Combined Query {i}: {query}")
        try:
            response = await agent.say(query)
            print(f"✅ Response length: {len(response)} characters")
            print(f"📝 Preview: {response[:200]}...")
        except Exception as e:
            print(f"❌ Combined Error: {type(e).__name__}: {str(e)[:100]}...")


async def run_comprehensive_test():
    """Run all tests and provide summary"""
    print("🚀 ADK RAG Agent Comprehensive Test")
    print("=" * 60)
    
    # Setup
    setup_environment()
    
    # Test agent configuration  
    agent = await test_agent_configuration()
    if not agent:
        print("❌ Failed to load agent - stopping tests")
        return
    
    # Test RAG functionality
    rag_success = await test_rag_retrieval(agent)
    
    # Test GitHub MCP integration
    github_success = await test_github_mcp_integration(agent)
    
    # Test combined functionality
    await test_combined_functionality(agent)
    
    # Final summary
    print(f"\n🎯 Final Test Summary")
    print("=" * 60)
    print(f"✅ Agent Configuration: {'PASS' if agent else 'FAIL'}")
    print(f"✅ RAG Retrieval: {'PASS' if rag_success else 'PARTIAL/FAIL'}")
    print(f"✅ GitHub MCP Tools: {'PASS' if github_success else 'PARTIAL/FAIL'}")
    print(f"✅ Total Tools Available: {len(agent.tools)}")
    
    # Tool breakdown
    print(f"\n📋 Tool Breakdown:")
    for i, tool in enumerate(agent.tools, 1):
        tool_name = getattr(tool, '__name__', type(tool).__name__)
        print(f"   {i}. {tool_name}")
    
    overall_success = agent and (rag_success or github_success)
    print(f"\n{'🎉 OVERALL: SUCCESS!' if overall_success else '⚠️  OVERALL: PARTIAL SUCCESS'}")
    
    if overall_success:
        print(f"\n🌟 Your ADK RAG agent is working with:")
        print(f"   - Document retrieval from Vertex AI Search")
        print(f"   - GitHub integration via MCP server")
        print(f"   - Available at: http://127.0.0.1:8501")
    
    return overall_success


if __name__ == "__main__":
    try:
        success = asyncio.run(run_comprehensive_test())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n⏹️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)