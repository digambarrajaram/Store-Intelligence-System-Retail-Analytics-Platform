terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.46.0"
    }
  }
}
provider "aws" {
  region = var.Store_ai_aws_region
}