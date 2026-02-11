"""GitHub Actions OIDC bootstrap stack.

Creates IAM roles for GitHub Actions CI/CD using OIDC authentication.
The OIDC provider is created if it doesn't exist, or imported if it does.

Usage:
    cdk deploy GitHubOIDCStack -c github_org=YOUR_ORG -c github_repo=YOUR_REPO
"""

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
)
from aws_cdk import (
    aws_iam as iam,
)
from constructs import Construct


class GitHubOIDCStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        github_org: str,
        github_repo: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # Get or create the GitHub OIDC provider
        provider = self._get_or_create_oidc_provider()

        # Deploy role - used for CDK deployments and container pushes
        repo_condition = f"repo:{github_org}/{github_repo}:*"
        deploy_role = iam.Role(
            self,
            "GitHubDeployRole",
            role_name="github-actions-deploy",
            max_session_duration=Duration.hours(1),
            assumed_by=iam.WebIdentityPrincipal(
                provider.open_id_connect_provider_arn,
                conditions={
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                    },
                    "StringLike": {
                        "token.actions.githubusercontent.com:sub": repo_condition,
                    },
                },
            ),
        )

        # PowerUserAccess for most AWS operations
        deploy_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("PowerUserAccess")
        )

        # CDK bootstrap role permissions
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                sid="CDKBootstrapAccess",
                actions=[
                    "iam:PassRole",
                    "iam:GetRole",
                    "iam:CreateRole",
                    "iam:DeleteRole",
                    "iam:AttachRolePolicy",
                    "iam:DetachRolePolicy",
                    "iam:PutRolePolicy",
                    "iam:DeleteRolePolicy",
                    "iam:TagRole",
                    "iam:UntagRole",
                ],
                resources=[f"arn:aws:iam::{self.account}:role/cdk-*"],
            )
        )

        # ECR permissions for container pushes
        deploy_role.add_to_policy(
            iam.PolicyStatement(
                sid="ECRAccess",
                actions=[
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                    "ecr:PutImage",
                    "ecr:InitiateLayerUpload",
                    "ecr:UploadLayerPart",
                    "ecr:CompleteLayerUpload",
                ],
                resources=["*"],
            )
        )

        # Security scan role - read-only for Prowler audits
        security_scan_role = iam.Role(
            self,
            "GitHubSecurityScanRole",
            role_name="github-actions-security-scan",
            max_session_duration=Duration.hours(1),
            assumed_by=iam.WebIdentityPrincipal(
                provider.open_id_connect_provider_arn,
                conditions={
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                    },
                    "StringLike": {
                        "token.actions.githubusercontent.com:sub": repo_condition,
                    },
                },
            ),
        )

        security_scan_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("SecurityAudit")
        )
        security_scan_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("ReadOnlyAccess")
        )

        # Outputs
        CfnOutput(
            self,
            "OIDCProviderArn",
            value=provider.open_id_connect_provider_arn,
            description="GitHub OIDC Provider ARN",
        )
        CfnOutput(
            self,
            "DeployRoleArn",
            value=deploy_role.role_arn,
            description="Deploy role ARN - add to GitHub secrets as AWS_DEPLOY_ROLE_ARN",
            export_name="GitHubDeployRoleArn",
        )
        CfnOutput(
            self,
            "SecurityScanRoleArn",
            value=security_scan_role.role_arn,
            description="Security scan role ARN - add to GitHub secrets",
            export_name="GitHubSecurityScanRoleArn",
        )

    def _get_or_create_oidc_provider(self) -> iam.IOpenIdConnectProvider:
        """Get existing GitHub OIDC provider or create a new one."""
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError

        provider_url = "token.actions.githubusercontent.com"
        provider_arn = f"arn:aws:iam::{self.account}:oidc-provider/{provider_url}"

        # Check if provider exists (requires AWS credentials at synth time)
        try:
            iam_client = boto3.client("iam")
            iam_client.get_open_id_connect_provider(OpenIDConnectProviderArn=provider_arn)
            # Provider exists, import it
            return iam.OpenIdConnectProvider.from_open_id_connect_provider_arn(
                self, "GitHubOIDC", provider_arn
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchEntity":
                # Provider doesn't exist, create it
                return iam.OpenIdConnectProvider(
                    self,
                    "GitHubOIDC",
                    url=f"https://{provider_url}",
                    client_ids=["sts.amazonaws.com"],
                )
            raise
        except NoCredentialsError:
            # No credentials at synth time, assume provider exists
            # (will fail at deploy if it doesn't)
            return iam.OpenIdConnectProvider.from_open_id_connect_provider_arn(
                self, "GitHubOIDC", provider_arn
            )
