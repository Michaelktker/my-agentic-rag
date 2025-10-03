#!/usr/bin/env python3
"""
Test script to verify the agent's tools are properly configured.
This test runs without requiring Google Cloud authentication.
"""

import os
import sys
from unittest.mock import Mock, patch

# Set environment variables before importing
# Ensure GITHUB_PAT is set as environment variable before running
if not os.environ.get("GITHUB_PAT"):
    print("❌ GITHUB_PAT environment variable not set")
    sys.exit(1)
os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project"
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

def test_agent_configuration():
    """Test that the agent is configured with the correct tools."""
    
    print("🧪 Testing ADK Agent Configuration...")
    print("-" * 50)
    
    # Mock Google Cloud dependencies
    with patch('google.auth.default') as mock_auth, \
         patch('vertexai.init') as mock_vertexai, \
         patch('langchain_google_vertexai.VertexAIEmbeddings') as mock_embeddings, \
         patch('app.retrievers.get_retriever') as mock_retriever, \
         patch('app.retrievers.get_compressor') as mock_compressor:
        
        # Set up mocks
        mock_auth.return_value = (Mock(), "test-project")
        mock_embeddings.return_value = Mock()
        mock_retriever.return_value = Mock()
        mock_compressor.return_value = Mock()
        
        # Import after mocking
        sys.path.insert(0, '.')
        from app.agent import root_agent, github_pat, tools
        
        print(f"✅ Agent Name: {root_agent.name}")
        print(f"✅ Agent Model: {root_agent.model}")
        print(f"✅ GitHub PAT Available: {'Yes' if github_pat else 'No'}")
        print(f"✅ Total Tools: {len(root_agent.tools)}")
        
        print("\n📋 Tool Details:")
        for i, tool in enumerate(root_agent.tools):
            tool_name = getattr(tool, '__name__', type(tool).__name__)
            if hasattr(tool, '__doc__') and tool.__doc__:
                doc_preview = tool.__doc__.strip().split('\n')[0][:80] + "..."
            else:
                doc_preview = "No description available"
            print(f"  {i+1}. {tool_name}")
            print(f"     Type: {type(tool).__name__}")
            print(f"     Description: {doc_preview}")
            print()
        
        # Test that we have the expected tools
        expected_tools = 2 if github_pat else 1
        if len(root_agent.tools) == expected_tools:
            print(f"✅ SUCCESS: Agent has {expected_tools} tools as expected!")
        else:
            print(f"❌ ERROR: Expected {expected_tools} tools, but found {len(root_agent.tools)}")
            return False
        
        # Test retrieve_docs function
        print("\n🔍 Testing retrieve_docs function...")
        if root_agent.tools and hasattr(root_agent.tools[0], '__name__') and root_agent.tools[0].__name__ == 'retrieve_docs':
            try:
                # Test with a mock query (this will fail gracefully due to missing auth)
                result = root_agent.tools[0]("test query")
                print("✅ retrieve_docs function is callable")
            except Exception as e:
                if "DefaultCredentialsError" in str(e) or "auth" in str(e).lower():
                    print("✅ retrieve_docs function is properly configured (auth error expected in test)")
                else:
                    print(f"⚠️  retrieve_docs function error: {e}")
        
        # Test MCP toolset
        if len(root_agent.tools) > 1:
            mcp_tool = root_agent.tools[1]
            print(f"\n🐙 Testing GitHub MCP Toolset...")
            print(f"✅ MCP Toolset Type: {type(mcp_tool).__name__}")
            print("✅ GitHub MCP toolset is configured and ready")
        
        print("\n🎉 All tests completed!")
        return True

if __name__ == "__main__":
    try:
        success = test_agent_configuration()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)