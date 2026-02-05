"""Frontend Stack - Amplify Hosting for React frontend."""

import aws_cdk.aws_amplify_alpha as amplify
from aws_cdk import SecretValue, Stack
from aws_cdk import aws_codebuild as codebuild
from constructs import Construct


class FrontendStack(Stack):
    """AWS Amplify Hosting for the React frontend."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        api_url: str,
        user_pool_id: str,
        user_pool_client_id: str,
        github_token_secret_name: str = "github-token",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Amplify App
        self.amplify_app = amplify.App(
            self,
            "FrontendApp",
            app_name="omnichannel-web",
            source_code_provider=amplify.GitHubSourceCodeProvider(
                owner="Walsen",
                repository="devsecops-poc",
                oauth_token=SecretValue.secrets_manager(github_token_secret_name),
            ),
            auto_branch_deletion=True,
            environment_variables={
                "VITE_API_URL": api_url,
                "VITE_COGNITO_USER_POOL_ID": user_pool_id,
                "VITE_COGNITO_CLIENT_ID": user_pool_client_id,
            },
            build_spec=codebuild.BuildSpec.from_object_to_yaml(
                {
                    "version": 1,
                    "applications": [
                        {
                            "appRoot": "web",
                            "frontend": {
                                "phases": {
                                    "preBuild": {"commands": ["npm ci"]},
                                    "build": {"commands": ["npm run build"]},
                                },
                                "artifacts": {
                                    "baseDirectory": "dist",
                                    "files": ["**/*"],
                                },
                                "cache": {"paths": ["node_modules/**/*"]},
                            },
                        }
                    ],
                }
            ),
        )

        # Main branch
        self.main_branch = self.amplify_app.add_branch(
            "main",
            auto_build=True,
            stage="PRODUCTION",
        )

        # Feature branches
        self.amplify_app.add_branch(
            "feature",
            auto_build=True,
            stage="DEVELOPMENT",
            branch_name="feature/*",
        )
