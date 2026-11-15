output "lambda_function_name" {
  value = aws_lambda_function.monitor.function_name
}

output "schedule" {
  value = "${aws_scheduler_schedule.monitor.schedule_expression} (${aws_scheduler_schedule.monitor.schedule_expression_timezone})"
}

output "ntfy_parameters" {
  value = [local.ntfy_topic_parameter, local.ntfy_error_topic_parameter]
}

output "table_name" {
  value = aws_dynamodb_table.prices.name
}
