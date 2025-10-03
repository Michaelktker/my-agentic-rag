#!/usr/bin/env python3
"""
Local test script to verify the updated agent configuration with 2 tools.
"""
import os
import sys
sys.path.append('/workspaces/my-agentic-rag')

# Set environment variables
# Ensure GITHUB_PAT is set as environment variable before running
if not os.environ.get("GITHUB_PAT"):
    print("❌ GITHUB_PAT environment variable not set")
    sys.exit(1)
os.environ["DATA_STORE_ID"] = "my-agentic-rag-datastore" 
os.environ["DATA_STORE_REGION"] = "us"

def test_agent_configuration():
    """Test the agent configuration and tools."""
    print("🚀 Testing ADK Agent Configuration...")
    print("=" * 50)
    
    try:
        from app.agent import root_agent, tools, github_mcp_toolset, retrieve_docs
        
        print(f"✅ Agent loaded successfully!")
        print(f"📊 Total tools: {len(tools)}")
        
        for i, tool in enumerate(tools):
            tool_name = getattr(tool, '__name__', type(tool).__name__)
            print(f"  {i+1}. {tool_name}")
            
        print(f"\n🔧 Tool Details:")
        print(f"  - First tool: {type(tools[0]).__name__}")
        print(f"  - Second tool: {tools[1].__name__ if hasattr(tools[1], '__name__') else 'retrieve_docs function'}")
        
        print(f"\n🤖 Agent Details:")
        print(f"  - Name: {root_agent.name}")
        print(f"  - Model: {root_agent.model}")
        print(f"  - Tools count: {len(root_agent.tools)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading agent: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_retrieve_docs():
    """Test the RAG retrieval function."""
    print("\n🧪 Testing RAG retrieval...")
    try:
        from app.agent import retrieve_docs
        result = retrieve_docs("pandas dataframe")
        
        if "error" in result.lower():
            print(f"⚠️ RAG retrieval had an issue: {result[:200]}...")
        else:
            print(f"✅ RAG retrieval working! Retrieved {len(result)} characters")
            print(f"📄 Preview: {result[:150]}...")
        return True
    except Exception as e:
        print(f"❌ RAG retrieval failed: {e}")
        return False

if __name__ == "__main__":
    print("🎯 Local Agent Test - Updated Configuration")
    print("=" * 60)
    
    # Test configuration
    config_ok = test_agent_configuration()
    
    # Test RAG if config is ok
    if config_ok:
        test_retrieve_docs()
    
    print("\n" + "=" * 60)
    print("✨ Test Complete!")
    print("🌐 Web interface available at: http://127.0.0.1:8000")
    print("\n💡 Test queries to try in the web interface:")
    print("  RAG: 'How to save pandas dataframe to CSV?'")
    print("  GitHub: 'Search Python repositories on GitHub'")
    print("  Combined: 'Find GitHub repos about pandas and explain usage'")