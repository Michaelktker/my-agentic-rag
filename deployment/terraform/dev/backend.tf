terraform {
  backend "gcs" {
    bucket = "production-adk-terraform-state"
    prefix = "my-agentic-rag/dev"
  }
}
