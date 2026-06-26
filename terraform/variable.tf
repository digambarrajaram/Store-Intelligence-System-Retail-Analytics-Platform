# ── OCI Provider Variables ──────────────────────────────────────────────────

variable "oci_region" {
  type        = string
  default     = "ap-mumbai-1"
  description = "OCI region"
}

variable "tenancy_ocid" {
  type        = string
  description = "OCI tenancy OCID"
  sensitive   = true
}

variable "user_ocid" {
  type        = string
  description = "OCI user OCID"
  sensitive   = true
}

variable "fingerprint" {
  type        = string
  description = "API key fingerprint"
  sensitive   = true
}

variable "private_key_path" {
  type        = string
  description = "Path to API private key PEM file"
  default     = "~/.oci/oci_api_key.pem"
}

# ── Compute Variables ───────────────────────────────────────────────────────

variable "compartment_ocid" {
  type        = string
  description = "OCI compartment OCID where resources will be created"
  sensitive   = true
}

variable "instance_name" {
  type        = string
  default     = "store-intelligence"
  description = "Compute instance display name"
}

variable "instance_shape" {
  type        = string
  default     = "VM.Standard.A1.Flex"
  description = "OCI compute shape (Ampere A1 ARM64 — Always Free eligible)"
}

variable "instance_ocpus" {
  type        = number
  default     = 4
  description = "Number of OCPUs (4 is max Always Free)"
}

variable "instance_memory_gb" {
  type        = number
  default     = 24
  description = "Memory in GB (24 is max Always Free)"
}

variable "boot_volume_size_gb" {
  type        = number
  default     = 100
  description = "Boot volume size in GB (200 GB Always Free total)"
}

variable "ssh_public_key" {
  type        = string
  description = "SSH public key for instance access"
}

variable "my_public_ip" {
  type        = string
  default     = "0.0.0.0/0"
  description = "Your public IP in CIDR notation for SSH restriction (e.g., 1.2.3.4/32)"
}

# ── Network Variables ───────────────────────────────────────────────────────

variable "vcn_cidr" {
  type        = string
  default     = "10.0.0.0/16"
  description = "VCN CIDR block"
}

variable "subnet_cidr" {
  type        = string
  default     = "10.0.1.0/24"
  description = "Subnet CIDR block"
}
