"""Frontend Stack - AWS Amplify Hosting for React application."""

from aws_cdk import (
    CfnOutput,
    SecretValue,
    Stack,
)
from aws_cdk import (
    aws_amplify as amplify,
)
from constructs import Construct


class FrontendStack(Stack):
    """Amplify Hosting for the certification announcer frontend."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        cognito_user_pool_id: str,
        cognito_client_id: str,
        cognito_domain: str,
        api_url: str,
        github_owner: str = "Walsen",
        github_repo: str = "devsecops-poc",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Amplify App using L1 construct
        self.amplify_app = amplify.CfnApp(
            self,
            "CertificationAnnouncerApp",
            name="aws-certification-announcer",
            repository=f"https://github.com/{github_owner}/{github_repo}",
            access_token=SecretValue.secrets_manager("github/oauth-token").unsafe_unwrap(),
            enable_branch_auto_deletion=True,
            environment_variables=[
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="VITE_API_URL",
                    value=api_url,
                ),
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="VITE_COGNITO_USER_POOL_ID",
                    value=cognito_user_pool_id,
                ),
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="VITE_COGNITO_CLIENT_ID",
                    value=cognito_client_id,
                ),
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="VITE_COGNITO_DOMAIN",
                    value=cognito_domain,
                ),
            ],
            build_spec="""
version: 1
frontend:
  phases:
    preBuild:
      commands:
        - cd web
        - npm ci
    build:
      commands:
        - npm run build
  artifacts:
    baseDirectory: web/dist
    files:
      - '**/*'
  cache:
    paths:
      - web/node_modules/**/*
""",
        )

        # Main branch
        self.main_branch = amplify.CfnBranch(
            self,
            "MainBranch",
            app_id=self.amplify_app.attr_app_id,
            branch_name="main",
            enable_auto_build=True,
            stage="PRODUCTION",
        )

        # Outputs
        CfnOutput(
            self,
            "AmplifyAppId",
            value=self.amplify_app.attr_app_id,
            description="Amplify App ID",
        )

        CfnOutput(
            self,
            "AmplifyAppUrl",
            value=f"https://main.{self.amplify_app.attr_default_domain}",
            description="Amplify App URL",
        )
