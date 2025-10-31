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

# Cloud SQL PostgreSQL instances for ADK session persistence (Staging & Production)
resource "google_sql_database_instance" "adk_sessions" {
  for_each         = local.deploy_project_ids
  name             = "adk-sessions-${each.key}"
  database_version = "POSTGRES_15"
  region           = var.region
  project          = each.value

  settings {
    tier = each.key == "staging" ? "db-f1-micro" : "db-g1-small" # Staging: $7/mo, Prod: $25/mo
    
    disk_size    = each.key == "staging" ? 10 : 20 # GB
    disk_type    = "PD_SSD"
    
    availability_type = each.key == "production" ? "REGIONAL" : "ZONAL" # HA for production
    
    backup_configuration {
      enabled                        = true
      start_time                     = "03:00"
      point_in_time_recovery_enabled = each.key == "production" # Only prod needs PITR
      transaction_log_retention_days = each.key == "production" ? 7 : 1
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = null
      require_ssl     = false
    }

    database_flags {
      name  = "max_connections"
      value = each.key == "production" ? "200" : "100"
    }

    maintenance_window {
      day          = 7 # Sunday
      hour         = 3
      update_track = "stable"
    }
  }

  deletion_protection = each.key == "production" # Protect production

  depends_on = [google_project_service.services]
}

# Databases for ADK sessions
resource "google_sql_database" "adk_sessions_db" {
  for_each = local.deploy_project_ids
  name     = "adk_sessions"
  instance = google_sql_database_instance.adk_sessions[each.key].name
  project  = each.value
}

# Database users for ADK application
resource "google_sql_user" "adk_app_user" {
  for_each = local.deploy_project_ids
  name     = "adk_app"
  instance = google_sql_database_instance.adk_sessions[each.key].name
  password = random_password.adk_db_password[each.key].result
  project  = each.value
}

# Generate secure random passwords for each environment
resource "random_password" "adk_db_password" {
  for_each = local.deploy_project_ids
  length   = 32
  special  = true
}

# Store database passwords in Secret Manager
resource "google_secret_manager_secret" "adk_db_password" {
  for_each  = local.deploy_project_ids
  secret_id = "adk-db-password"
  project   = each.value

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret_version" "adk_db_password" {
  for_each    = local.deploy_project_ids
  secret      = google_secret_manager_secret.adk_db_password[each.key].id
  secret_data = random_password.adk_db_password[each.key].result
}

# Store database connection strings in Secret Manager
resource "google_secret_manager_secret" "adk_db_connection" {
  for_each  = local.deploy_project_ids
  secret_id = "adk-db-connection"
  project   = each.value

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret_version" "adk_db_connection" {
  for_each = local.deploy_project_ids
  secret   = google_secret_manager_secret.adk_db_connection[each.key].id
  secret_data = "postgresql://${google_sql_user.adk_app_user[each.key].name}:${random_password.adk_db_password[each.key].result}@/${google_sql_database.adk_sessions_db[each.key].name}?host=/cloudsql/${google_sql_database_instance.adk_sessions[each.key].connection_name}"
}

# Output the connection details
output "cloudsql_connection_names" {
  value = {
    for k, v in google_sql_database_instance.adk_sessions :
    k => v.connection_name
  }
  description = "Cloud SQL connection names for each environment"
}

output "cloudsql_database_names" {
  value = {
    for k, v in google_sql_database.adk_sessions_db :
    k => v.name
  }
  description = "Database names for ADK sessions in each environment"
}
