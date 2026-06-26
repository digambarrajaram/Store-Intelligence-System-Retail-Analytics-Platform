output "instance_id" {
  value       = oci_core_instance.store_instance.id
  description = "OCI instance OCID"
}

output "public_ip" {
  value       = oci_core_instance.store_instance.public_ip
  description = "Public IP address of the instance"
}

output "dashboard_url" {
  value       = "http://${oci_core_instance.store_instance.public_ip}:3000"
  description = "Dashboard URL"
}

output "api_url" {
  value       = "http://${oci_core_instance.store_instance.public_ip}:8000"
  description = "API base URL"
}

output "grafana_url" {
  value       = "http://${oci_core_instance.store_instance.public_ip}:3001"
  description = "Grafana URL (admin/admin)"
}

output "prometheus_url" {
  value       = "http://${oci_core_instance.store_instance.public_ip}:9090"
  description = "Prometheus URL"
}
