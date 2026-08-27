###############################################################################
# API Gateway - HTTP API for the KB UI
# - GET  /search   -> search-lambda
# - POST /feedback -> feedback-lambda
# - GET  /health   -> search-lambda (no auth)
#
# Auth: IAM (SigV4) by default. CloudFront adds CORS handling.
###############################################################################

terraform {
  required_version = ">= 1.9.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.50" }
  }
}

variable "name_prefix"      { type = string }
variable "search_lambda"    { type = string }
variable "feedback_lambda"  { type = string }
variable "common_tags"      { type = map(string); default = {} }

resource "aws_apigatewayv2_api" "this" {
  name          = "${var.name_prefix}-api"
  protocol_type = "HTTP"
  description   = "DataCurator KB API"

  cors_configuration {
    allow_origins = ["*"]  # tighten in production
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization", "X-Amz-Date", "X-Amz-Security-Token"]
    max_age       = 300
  }

  tags = var.common_tags
}

resource "aws_apigatewayv2_stage" "this" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true
  tags        = var.common_tags
}

# --- /search ---

resource "aws_apigatewayv2_integration" "search" {
  api_id             = aws_apigatewayv2_api.this.id
  integration_type   = "AWS_PROXY"
  integration_uri    = var.search_lambda
  integration_method = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "search" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "GET /search"
  target    = "integrations/${aws_apigatewayv2_integration.search.id}"
}

# --- /feedback ---

resource "aws_apigatewayv2_integration" "feedback" {
  api_id             = aws_apigatewayv2_api.this.id
  integration_type   = "AWS_PROXY"
  integration_uri    = var.feedback_lambda
  integration_method = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "feedback" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "POST /feedback"
  target    = "integrations/${aws_apigatewayv2_integration.feedback.id}"
}

# --- /health (no auth) ---

resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.search.id}"
}

# --- Lambda permissions for API Gateway ---

resource "aws_lambda_permission" "search" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.search_lambda
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

resource "aws_lambda_permission" "feedback" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.feedback_lambda
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

output "api_id"     { value = aws_apigatewayv2_api.this.id }
output "api_url"    { value = aws_apigatewayv2_api.this.api_endpoint }
output "stage_name" { value = aws_apigatewayv2_stage.this.name }
