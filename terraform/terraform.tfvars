# ── OCI Terraform Variables ───────────────────────────────────────────────────
# Copy this file to terraform.tfvars and fill in your OCI credentials.
#
# HOW TO GET OCI CREDENTIALS:
#   1. Log in to cloud.oracle.com
#   2. Click your profile icon → "My Profile" → "API Keys" → "Add API Key"
#   3. Download the private key and note the fingerprint
#   4. Copy tenancy OCID and user OCID from your profile page
#   5. Create a compartment or use your root compartment (tenancy OCID)

# ── OCI Authentication (REQUIRED) ──────────────────────────────────────────

tenancy_ocid     = "ocid1.tenancy.oc1..aaaaaaaait4ejl4in67igvp6x36bzkw6pvyzqhhnorti3egce2a24meah6qa"
user_ocid        = "ocid1.user.oc1..aaaaaaaamcrszynqf6eaubuzcctsnuafn6rr7bjktp2joh4atuav3blodsba"
fingerprint      = "56:6b:2b:35:ec:92:72:b1:9f:cd:93:12:b3:32:b3:14"
private_key_path = "~/.oci/oci_api_key.pem"
compartment_ocid = "ocid1.domain.oc1..aaaaaaaa33xbajunifqvjl32ezayuggg6nyspq52fqv5u4blakttc2n6uz7q"  # or use your tenancy OCID

# ── OCI Region ─────────────────────────────────────────────────────────────

oci_region = "ap-mumbai-1"

# ── Compute ─────────────────────────────────────────────────────────────────

instance_name   = "store-intelligence"
instance_shape  = "VM.Standard.A1.Flex"
instance_ocpus  = 4
instance_memory_gb = 24
boot_volume_size_gb = 100

# ── SSH Key ─────────────────────────────────────────────────────────────────

ssh_public_key = "ssh-rsa $(cat ~/.oci/oci_api_key_public.pem) user@host"



# ── Security ────────────────────────────────────────────────────────────────

# Restrict SSH to your IP (use /32 for a single IP)
# Examples: "1.2.3.4/32" (single IP), "0.0.0.0/0" (any IP — UNSAFE!)
my_public_ip = "0.0.0.0/0"
