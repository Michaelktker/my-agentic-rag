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

# Cloud SQL PostgreSQL instance for ADK session persistence
resource "google_sql_database_instance" "adk_sessions" {
  name             = "adk-sessions-${var.dev_project_id}"
  database_version = "POSTGRES_15"
  region           = var.region
  project          = var.dev_project_id

  settings {
    tier = "db-g1-small" # Upgraded from f1-micro for better stability (~$27/month, 1.7GB RAM)
    # db-f1-micro (0.6GB RAM) was causing connection failures with PostgreSQL connection pools
    
    disk_size    = 10 # GB
    disk_type    = "PD_SSD"
    
    backup_configuration {
      enabled            = true
      start_time         = "03:00"
      point_in_time_recovery_enabled = false # Reduce costs in dev
    }

    ip_configuration {
      ipv4_enabled    = true
      private_network = null
      authorized_networks {
        name  = "allow-all"
        value = "0.0.0.0/0"
      }
    }

    database_flags {
      name  = "max_connections"
      value = "100"
    }
  }

  deletion_protection = false # Allow deletion in dev

  depends_on = [google_project_service.services]
}

# Database for ADK sessions
resource "google_sql_database" "adk_sessions_db" {
  name     = "adk_sessions"
  instance = google_sql_database_instance.adk_sessions.name
  project  = var.dev_project_id
}

# Database user for ADK application
resource "google_sql_user" "adk_app_user" {
  name     = "adk_app"
  instance = google_sql_database_instance.adk_sessions.name
  password = random_password.adk_db_password.result
  project  = var.dev_project_id
}

# Generate secure random password for database
resource "random_password" "adk_db_password" {
  length  = 32
  special = true
}

# Store database password in Secret Manager
resource "google_secret_manager_secret" "adk_db_password" {
  secret_id = "adk-db-password"
  project   = var.dev_project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret_version" "adk_db_password" {
  secret      = google_secret_manager_secret.adk_db_password.id
  secret_data = random_password.adk_db_password.result
}

# Store database connection string in Secret Manager
resource "google_secret_manager_secret" "adk_db_connection" {
  secret_id = "adk-db-connection"
  project   = var.dev_project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret_version" "adk_db_connection" {
  secret = google_secret_manager_secret.adk_db_connection.id
  secret_data = "postgresql://${google_sql_user.adk_app_user.name}:${random_password.adk_db_password.result}@/${google_sql_database.adk_sessions_db.name}?host=/cloudsql/${google_sql_database_instance.adk_sessions.connection_name}"
}

# Output the connection details
output "cloudsql_connection_name_dev" {
  value       = google_sql_database_instance.adk_sessions.connection_name
  description = "Cloud SQL connection name for dev"
}

output "cloudsql_database_name_dev" {
  value       = google_sql_database.adk_sessions_db.name
  description = "Database name for ADK sessions in dev"
}
