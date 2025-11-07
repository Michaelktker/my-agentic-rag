staging_project_id = "staging-adk"
prod_project_id = "production-adk"
cicd_runner_project_id = "production-adk"
region = "us-central1"
repository_name = "my-agentic-rag"
repository_owner = "Michaelktker"
host_connection_name = "git-my-agentic-rag"
create_cb_connection = true
create_repository = false
github_app_installation_id = "54681073"
github_pat_secret_id = "git-my-agentic-rag-github-oauthtoken-ddff64"
# IMPORTANT: Set fal_api_key via environment variable or command line
# Never commit actual API keys to version control
# Usage: terraform apply -var="fal_api_key=$FAL_KEY"
fal_api_key = ""
