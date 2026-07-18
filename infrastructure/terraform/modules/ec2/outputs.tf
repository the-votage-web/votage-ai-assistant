output "instance_id" {
  value = aws_instance.votage_ai_assistant.id
}

output "public_ip" {
  value = aws_instance.votage_ai_assistant.public_ip
}

output "public_dns" {
  value = aws_instance.votage_ai_assistant.public_dns
}
