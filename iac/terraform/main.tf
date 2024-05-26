# Ref: https://github.com/terraform-google-modules/terraform-google-kubernetes-engine/blob/master/examples/simple_autopilot_public
# To define that we will use GCP
terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
      version = "4.80.0" // Provider version
    }
  }
  required_version = "1.6.6" // Terraform version
}

// The library with methods for creating and
// managing the infrastructure in GCP, this will
// apply to all the resources in the project
provider "google" {
  project     = var.project_id
  region      = var.region
}

// Google Kubernetes Engine
resource "google_container_cluster" "my_gke" {
  name     = "mlops-gke"
  location = var.zone
 
  remove_default_node_pool = true
  initial_node_count       = 1
  
  # // Enable Istio (beta)
  # // https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/container_cluster#nested_istio_config
  # // not yet supported on Autopilot mode
  # addons_config {
  #   istio_config {
  #     disabled = false
  #     auth     = "AUTH_NONE"
  #   }
  # }
}

resource "google_container_node_pool" "my_gke_nodes" {
  name       = "primary-node-pool"
  cluster    = google_container_cluster.my_gke.name
  location   = google_container_cluster.my_gke.location

  node_config {
    machine_type = "e2-standard-4"  # Specify the machine type
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
    ]
  }

  autoscaling {
    min_node_count = 1
    max_node_count = 2
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  initial_node_count = 1
}

