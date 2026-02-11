"""API Stack - Lambda functions and API Gateway for REST API."""

from aws_cdk import Duration, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_kinesis as kinesis
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from constructs import Construct


class ApiStack(Stack):
    """API Gateway + Lambda functions for the REST API."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        main_table: dynamodb.Table,
        kinesis_stream: kinesis.Stream,
        media_bucket: s3.Bucket,
        user_pool: cognito.UserPool,
        user_pool_client_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Common environment variables
        common_env = {
            "TABLE_NAME": main_table.table_name,
            "KINESIS_STREAM_NAME": kinesis_stream.stream_name,
            "MEDIA_BUCKET": media_bucket.bucket_name,
            "COGNITO_USER_POOL_ID": user_pool.user_pool_id,
            "COGNITO_CLIENT_ID": user_pool_client_id,
            "LOG_LEVEL": "INFO",
        }

        # API Lambda function
        self.api_function = lambda_.Function(
            self,
            "ApiFunction",
            function_name="omnichannel-api",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="main.handler",
            code=lambda_.Code.from_asset("../api-lambda"),
            environment=common_env,
            timeout=Duration.seconds(30),
            memory_size=512,
            architecture=lambda_.Architecture.ARM_64,
            tracing=lambda_.Tracing.ACTIVE,
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

        # Grant permissions
        main_table.grant_read_write_data(self.api_function)
        kinesis_stream.grant_write(self.api_function)
        media_bucket.grant_read_write(self.api_function)

        # API Gateway
        self.api = apigw.RestApi(
            self,
            "OmnichannelApi",
            rest_api_name="Omnichannel Publisher API",
            description="Serverless API for Omnichannel Publisher",
            deploy_options=apigw.StageOptions(
                stage_name="v1",
                throttling_rate_limit=1000,
                throttling_burst_limit=2000,
                logging_level=apigw.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                metrics_enabled=True,
            ),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization", "X-Api-Key"],
            ),
        )

        # Cognito authorizer
        authorizer = apigw.CognitoUserPoolsAuthorizer(
            self,
            "CognitoAuthorizer",
            cognito_user_pools=[user_pool],
        )

        # Lambda integration
        api_integration = apigw.LambdaIntegration(
            self.api_function,
            proxy=True,
        )

        # Health check (no auth)
        health = self.api.root.add_resource("health")
        health.add_method("GET", api_integration)

        # API routes with auth - proxy all other routes
        api_v1 = self.api.root.add_resource("api").add_resource("v1")
        api_v1.add_proxy(
            default_integration=api_integration,
            any_method=True,
            default_method_options=apigw.MethodOptions(
                authorizer=authorizer,
                authorization_type=apigw.AuthorizationType.COGNITO,
            ),
        )

        # Export API URL
        self.api_url = self.api.url
