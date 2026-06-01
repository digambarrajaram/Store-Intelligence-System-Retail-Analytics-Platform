variable "Store_ai_instance_type" {
  type        = string
  default     = "t3.xlarge"
  description = "EC2 instance type"
}

variable "Store_ai_key_name" {
  type        = string
  default     = "elk-stack-server_keypair"
  description = "EC2 key pair"
}

variable "Store_ai_instance_name" {
  type        = string
  default     = "store-instance"
  description = "EC2 instance name"
}

variable "Store_ai_aws_region" {
  type        = string
  default     = "ap-south-1"
  description = "AWS Region"
}

variable "Store_ai_project" {
  type        = string
  default     = "store-ai-stack"
  description = "Project name"
}

variable "Store_ai_internet_route" {
  default     = "0.0.0.0/0"
  description = "Internet route"
}
