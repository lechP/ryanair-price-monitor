variable "region" {
  type    = string
  default = "eu-central-1"
}

variable "project" {
  type    = string
  default = "ryanair-price-monitor"
}

variable "schedule_expression" {
  description = "EventBridge Scheduler expression, evaluated in schedule_timezone."
  type        = string
  default     = "cron(0 7-21/2 * * ? *)"
}

variable "schedule_timezone" {
  type    = string
  default = "Europe/Warsaw"
}

variable "lambda_package" {
  description = "Path to the zip built by scripts/build-lambda.sh."
  type        = string
  default     = "../dist/lambda.zip"
}

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "ntfy_server" {
  type    = string
  default = "https://ntfy.sh"
}

variable "daily_summary_hour" {
  description = "Local hour (schedule_timezone) whose scheduled run sends the daily summary; must match a run in schedule_expression."
  type        = number
  default     = 21
}
