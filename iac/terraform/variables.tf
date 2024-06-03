// Variables to use accross the project
// which can be accessed by var.project_id
variable "project_id" {
  description = "The project ID to host the cluster in"
  default     = "evocative-reef-424101-n0"
}

variable "region" {
  description = "The region the cluster in"
  default     = "asia-southeast1"
}


variable "zone" {
  description = "The zone the cluster in"
  default     = "asia-southeast1-b"
}
