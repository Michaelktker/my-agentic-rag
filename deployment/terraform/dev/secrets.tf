# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# FAL API Key Secret Manager
resource "google_secret_manager_secret" "fal_api_key" {
  for_each = {
    staging = var.dev_project_id
  }
  
  project   = each.value
  secret_id = "fal-api-key"
  
  replication {
    auto {}
  }
  
  labels = {
    created-by = "adk"
    purpose    = "fal-ai-mcp-integration"
    environment = "staging"
  }
  
  depends_on = [google_project_service.services]
}

# Create FAL API key secret version
resource "google_secret_manager_secret_version" "fal_api_key" {
  for_each = {
    staging = var.dev_project_id
  }
  
  secret      = google_secret_manager_secret.fal_api_key[each.key].id
  secret_data = var.fal_api_key
}