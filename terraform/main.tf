# Fetch an Ubuntu 22.04 LTS Machine Image automatically
data "aws_ami" "ubuntu" {
  most_recent = true
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
  owners = ["099720109477"] # Canonical
}

resource "aws_instance" "store_instance" {
    ami = data.aws_ami.ubuntu.id
    instance_type = var.Store_ai_instance_type
    key_name = var.Store_ai_key_name

    # IMDSv2 enforced (security best practice — required by AWS Security Hub)
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"   # enforces IMDSv2
    http_put_response_hop_limit = 1
  }

  root_block_device {
    volume_size           = 30
    volume_type           = "gp3"
    encrypted             = true   # EBS encryption at rest
    delete_on_termination = true
  }

  user_data = <<-EOF
    #!/bin/bash
    apt-get update -y
    apt-get install -y docker.io docker-compose-plugin git

    # Allow docker without sudo
    usermod -aG docker ubuntu


    # Clone your repo (update URL after pushing to GitHub)
    # git clone https://github.com/digambarrajaram/store-intelligence-system.git /home/ubuntu/
  EOF

    tags = {
      Name = var.Store_ai_instance_name
      Project = var.Store_ai_project
    }
}

resource "aws_security_group" "store_sg" {
    name = "store-ai-stack-sg"
    description = "Security group for ai stack"

    tags = {
      Name = "store-stack-sg"
      Project = var.Store_ai_project
    }
}

resource "aws_vpc_security_group_ingress_rule" "ssh" {
  security_group_id = aws_security_group.store_sg.id
  cidr_ipv4 = var.Store_ai_internet_route
  ip_protocol = "tcp"
  from_port = 22
  to_port = 22
}

resource "aws_vpc_security_group_ingress_rule" "https" {
  security_group_id = aws_security_group.store_sg.id
  cidr_ipv4 = var.Store_ai_internet_route
  ip_protocol = "tcp"
  from_port = 443
  to_port = 443
}
resource "aws_vpc_security_group_ingress_rule" "port8000" {
  security_group_id = aws_security_group.store_sg.id
  cidr_ipv4 = var.Store_ai_internet_route
  ip_protocol = "tcp"
  from_port = 8000 
  to_port = 8000 
}
resource "aws_vpc_security_group_ingress_rule" "port3000" {
  security_group_id = aws_security_group.store_sg.id
  cidr_ipv4 = var.Store_ai_internet_route
  ip_protocol = "tcp"
  from_port = 3000 
  to_port = 3000 
}

resource "aws_vpc_security_group_ingress_rule" "port3001" {
  security_group_id = aws_security_group.store_sg.id
  cidr_ipv4 = var.Store_ai_internet_route
  ip_protocol = "tcp"
  from_port = 3001 
  to_port = 3001 
}

resource "aws_vpc_security_group_ingress_rule" "port9090" {
  security_group_id = aws_security_group.store_sg.id
  cidr_ipv4 = var.Store_ai_internet_route
  ip_protocol = "tcp"
  from_port = 9090 
  to_port = 9090 
}
resource "aws_vpc_security_group_ingress_rule" "http" {
  security_group_id = aws_security_group.store_sg.id
  cidr_ipv4 = var.Store_ai_internet_route
  ip_protocol = "tcp"
  from_port = 80
  to_port = 80
}
resource "aws_vpc_security_group_ingress_rule" "port8001" {
  security_group_id = aws_security_group.store_sg.id
  cidr_ipv4 = var.Store_ai_internet_route
  ip_protocol = "tcp"
  from_port = 8001
  to_port = 8001
}
 
resource "aws_vpc_security_group_egress_rule" "allow_all_outbound" {
  security_group_id = aws_security_group.store_sg.id
  cidr_ipv4         = var.Store_ai_internet_route
  ip_protocol       = "-1" # Semantically represents all protocols
}