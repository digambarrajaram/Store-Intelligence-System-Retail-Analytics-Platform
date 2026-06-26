# ── OCI Store Intelligence System — Always Free Tier ─────────────────────────
# Resources: VCN, subnet, internet gateway, security list, Ampere A1 compute

# ── Networking ──────────────────────────────────────────────────────────────

resource "oci_core_vcn" "store_vcn" {
  compartment_id = var.compartment_ocid
  cidr_block     = var.vcn_cidr
  display_name   = "store-intelligence-vcn"
  dns_label      = "storevcn"
}

resource "oci_core_internet_gateway" "store_igw" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.store_vcn.id
  display_name   = "store-intelligence-igw"
}

resource "oci_core_default_route_table" "store_route" {
  manage_default_resource_id = oci_core_vcn.store_vcn.default_route_table_id

  route_rules {
    destination       = "0.0.0.0/0"
    network_entity_id = oci_core_internet_gateway.store_igw.id
  }
}

resource "oci_core_subnet" "store_subnet" {
  compartment_id    = var.compartment_ocid
  vcn_id            = oci_core_vcn.store_vcn.id
  cidr_block        = var.subnet_cidr
  display_name      = "store-intelligence-subnet"
  dns_label         = "storesubnet"
  security_list_ids = [oci_core_security_list.store_sl.id]
  route_table_id    = oci_core_default_route_table.store_route.id
}

# ── Security List ───────────────────────────────────────────────────────────

resource "oci_core_security_list" "store_sl" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.store_vcn.id
  display_name   = "store-intelligence-sl"

  # SSH (TCP 22) from your IP only
  ingress_security_rules {
    protocol    = "6"
    source      = var.my_public_ip
    source_type = "CIDR_BLOCK"
    stateless   = false
    tcp_options {
      min = 22
      max = 22
    }
  }

  # HTTP (80) and HTTPS (443) from anywhere
  dynamic "ingress_security_rules" {
    for_each = [80, 443]
    content {
      protocol    = "6"
      source      = "0.0.0.0/0"
      source_type = "CIDR_BLOCK"
      stateless   = false
      tcp_options {
        min = ingress_security_rules.value
        max = ingress_security_rules.value
      }
    }
  }

  # Dashboard (:3000), API (:8000), Grafana (:3001), Prometheus (:9090)
  dynamic "ingress_security_rules" {
    for_each = [3000, 8000, 3001, 9090]
    content {
      protocol    = "6"
      source      = "0.0.0.0/0"
      source_type = "CIDR_BLOCK"
      stateless   = false
      tcp_options {
        min = ingress_security_rules.value
        max = ingress_security_rules.value
      }
    }
  }

  # ICMP for ping diagnostics
  ingress_security_rules {
    protocol    = "1"
    source      = "0.0.0.0/0"
    source_type = "CIDR_BLOCK"
    stateless   = false
    icmp_options {
      type = 8
      code = 0
    }
  }

  # Allow all outbound (needed for Docker pulls, package installs)
  egress_security_rules {
    protocol        = "all"
    destination     = "0.0.0.0/0"
    destination_type = "CIDR_BLOCK"
    stateless       = false
  }
}

# ── Compute Instance ────────────────────────────────────────────────────────

resource "oci_core_instance" "store_instance" {
  compartment_id      = var.compartment_ocid
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
  display_name        = var.instance_name
  shape               = var.instance_shape

  shape_config {
    ocpus         = var.instance_ocpus
    memory_in_gbs = var.instance_memory_gb
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.store_subnet.id
    assign_public_ip = true
    display_name     = "store-intelligence-vnic"
  }

  source_details {
    source_type = "image"
    source_id   = data.oci_core_images.ubuntu_2204_arm64.images[0].id
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data           = base64encode(data.cloudinit_config.store_setup.rendered)
  }

  preserve_boot_volume = false
}

# ── Data Sources ────────────────────────────────────────────────────────────

data "oci_identity_availability_domains" "ads" {
  compartment_id = var.tenancy_ocid
}

data "oci_core_images" "ubuntu_2204_arm64" {
  compartment_id          = var.compartment_ocid
  operating_system        = "Canonical Ubuntu"
  operating_system_version = "22.04"
  shape                   = var.instance_shape

  filter {
    name   = "display_name"
    values = ["Canonical-Ubuntu-22.04-aarch64-*"]
    regex  = true
  }
}

# ── Cloud-Init ──────────────────────────────────────────────────────────────

data "cloudinit_config" "store_setup" {
  gzip          = false
  base64_encode = false

  part {
    content_type = "text/cloud-config"
    content      = file("${path.module}/cloud-init.yml")
  }
}
