"""Auth Stack - Cognito User Pool with social identity providers."""

from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import (
    aws_cognito as cognito,
)
from aws_cdk import (
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


class AuthStack(Stack):
    """Cognito User Pool with Google, GitHub, and LinkedIn identity providers."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Secrets for OAuth providers
        self.oauth_secrets = secretsmanager.Secret(
            self,
            "OAuthSecrets",
            secret_name="omnichannel/oauth-credentials",
            description="OAuth credentials for social identity providers",
        )

        # Cognito User Pool
        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name="omnichannel-users",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
                fullname=cognito.StandardAttribute(required=False, mutable=True),
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.RETAIN,
            advanced_security_mode=cognito.AdvancedSecurityMode.ENFORCED,
        )

        # User Pool Client
        self.user_pool_client = self.user_pool.add_client(
            "WebClient",
            user_pool_client_name="omnichannel-web",
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=True,
                    implicit_code_grant=True,
                ),
                scopes=[
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.PROFILE,
                ],
                callback_urls=[
                    "http://localhost:5173/callback",
                    "https://app.example.com/callback",
                ],
                logout_urls=[
                    "http://localhost:5173",
                    "https://app.example.com",
                ],
            ),
            access_token_validity=Duration.hours(1),
            id_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(30),
            prevent_user_existence_errors=True,
        )

        # User Pool Domain
        self.user_pool_domain = self.user_pool.add_domain(
            "Domain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix="omnichannel-auth",
            ),
        )

        # Export values
        self.user_pool_id = self.user_pool.user_pool_id
        self.user_pool_client_id = self.user_pool_client.user_pool_client_id
