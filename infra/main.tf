data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  # SecureString parameters created outside Terraform (see README) so topic names never reach state.
  ntfy_topic_parameter       = "/${var.project}/ntfy-topic"
  ntfy_error_topic_parameter = "/${var.project}/ntfy-error-topic"
  parameter_arn_prefix       = "arn:${data.aws_partition.current.partition}:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project}"
  lambda_package_path        = "${path.module}/${var.lambda_package}"
}

# --- Lambda -----------------------------------------------------------------

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.project}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "monitor" {
  function_name    = var.project
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  architectures    = ["arm64"]
  handler          = "ryanair_price_monitor.handler.lambda_handler"
  filename         = local.lambda_package_path
  source_code_hash = filebase64sha256(local.lambda_package_path)
  memory_size      = 256
  timeout          = 120

  environment {
    variables = {
      NTFY_TOPIC_PARAMETER       = local.ntfy_topic_parameter
      NTFY_ERROR_TOPIC_PARAMETER = local.ntfy_error_topic_parameter
      NTFY_SERVER                = var.ntfy_server
    }
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.lambda.name
  }
}

# Scheduler invokes asynchronously; disable Lambda's own retries so a failure
# produces one error notification instead of three.
resource "aws_lambda_function_event_invoke_config" "monitor" {
  function_name          = aws_lambda_function.monitor.function_name
  maximum_retry_attempts = 0
}

resource "aws_iam_role" "lambda" {
  name = "${var.project}-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "lambda" {
  name = "runtime"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.lambda.arn}:*"
      },
      {
        # Parameters use the AWS managed aws/ssm key, whose key policy already allows decryption via SSM.
        Effect   = "Allow"
        Action   = ["ssm:GetParameters"]
        Resource = ["${local.parameter_arn_prefix}/ntfy-topic", "${local.parameter_arn_prefix}/ntfy-error-topic"]
      },
    ]
  })
}

# --- Schedule ---------------------------------------------------------------

resource "aws_scheduler_schedule" "monitor" {
  name                         = var.project
  schedule_expression          = var.schedule_expression
  schedule_expression_timezone = var.schedule_timezone

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.monitor.arn
    role_arn = aws_iam_role.scheduler.arn

    retry_policy {
      maximum_retry_attempts = 0
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name = "${var.project}-scheduler"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
      }
    }]
  })
}

resource "aws_iam_role_policy" "scheduler" {
  name = "invoke-lambda"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.monitor.arn
    }]
  })
}
