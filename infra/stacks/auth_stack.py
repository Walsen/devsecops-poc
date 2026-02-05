from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    SecretValue,
    Stack,
)
from aws_cdk import (
    aws_cognito as cognito,
)
from constructs import Construct


class AuthStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Cognito User Pool
        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name="omnichannel-users",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(
                email=True,
                username=True,
            ),
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
        )

        # ============================================================
        # Social Identity Providers
        # Credentials should be stored in Secrets Manager and referenced here
        # ============================================================

        # Google Identity Provider
        google_provider = cognito.UserPoolIdentityProviderGoogle(
            self,
            "GoogleProvider",
            user_pool=self.user_pool,
            client_id=SecretValue.secrets_manager(
                "omnichannel/oauth/google", json_field="client_id"
            ).unsafe_unwrap(),
            client_secret_value=SecretValue.secrets_manager(
                "omnichannel/oauth/google", json_field="client_secret"
            ),
            scopes=["profile", "email", "openid"],
            attribute_mapping=cognito.AttributeMapping(
                email=cognito.ProviderAttribute.GOOGLE_EMAIL,
                fullname=cognito.ProviderAttribute.GOOGLE_NAME,
                profile_picture=cognito.ProviderAttribute.GOOGLE_PICTURE,
            ),
        )

        # GitHub Identity Provider (OIDC)
        github_provider = cognito.UserPoolIdentityProviderOidc(
            self,
            "GitHubProvider",
            user_pool=self.user_pool,
            name="GitHub",
            client_id=SecretValue.secrets_manager(
                "omnichannel/oauth/github", json_field="client_id"
            ).unsafe_unwrap(),
            client_secret=SecretValue.secrets_manager(
                "omnichannel/oauth/github", json_field="client_secret"
            ).unsafe_unwrap(),
            issuer_url="https://token.actions.githubusercontent.com",  # GitHub OIDC
            endpoints=cognito.OidcEndpoints(
                authorization="https://github.com/login/oauth/authorize",
                token="https://github.com/login/oauth/access_token",
                user_info="https://api.github.com/user",
                jwks_uri="https://token.actions.githubusercontent.com/.well-known/jwks",
            ),
            scopes=["openid", "user:email", "read:user"],
            attribute_mapping=cognito.AttributeMapping(
                email=cognito.ProviderAttribute.other("email"),
                preferred_username=cognito.ProviderAttribute.other("login"),
                fullname=cognito.ProviderAttribute.other("name"),
                profile_picture=cognito.ProviderAttribute.other("avatar_url"),
            ),
        )

        # LinkedIn Identity Provider (OIDC)
        linkedin_provider = cognito.UserPoolIdentityProviderOidc(
            self,
            "LinkedInProvider",
            user_pool=self.user_pool,
            name="LinkedIn",
            client_id=SecretValue.secrets_manager(
                "omnichannel/oauth/linkedin", json_field="client_id"
            ).unsafe_unwrap(),
            client_secret=SecretValue.secrets_manager(
                "omnichannel/oauth/linkedin", json_field="client_secret"
            ).unsafe_unwrap(),
            issuer_url="https://www.linkedin.com/oauth",
            endpoints=cognito.OidcEndpoints(
                authorization="https://www.linkedin.com/oauth/v2/authorization",
                token="https://www.linkedin.com/oauth/v2/accessToken",
                user_info="https://api.linkedin.com/v2/userinfo",
                jwks_uri="https://www.linkedin.com/oauth/openid/jwks",
            ),
            scopes=["openid", "profile", "email"],
            attribute_mapping=cognito.AttributeMapping(
                email=cognito.ProviderAttribute.other("email"),
                fullname=cognito.ProviderAttribute.other("name"),
                profile_picture=cognito.ProviderAttribute.other("picture"),
            ),
        )

        # User Pool Client (for API authentication)
        # Must be created after identity providers to include them
        self.user_pool_client = self.user_pool.add_client(
            "ApiClient",
            user_pool_client_name="omnichannel-api-client",
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=True,
                    implicit_code_grant=False,
                ),
                scopes=[
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.PROFILE,
                ],
                callback_urls=["http://localhost:3000/callback"],
                logout_urls=["http://localhost:3000/logout"],
            ),
            supported_identity_providers=[
                cognito.UserPoolClientIdentityProvider.COGNITO,
                cognito.UserPoolClientIdentityProvider.GOOGLE,
                cognito.UserPoolClientIdentityProvider.custom("GitHub"),
                cognito.UserPoolClientIdentityProvider.custom("LinkedIn"),
            ],
            access_token_validity=Duration.hours(1),
            id_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(30),
            prevent_user_existence_errors=True,
        )

        # Ensure client is created after providers
        self.user_pool_client.node.add_dependency(google_provider)
        self.user_pool_client.node.add_dependency(github_provider)
        self.user_pool_client.node.add_dependency(linkedin_provider)

        # User Pool Domain (for hosted UI)
        self.user_pool_domain = self.user_pool.add_domain(
            "Domain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix="omnichannel-auth",  # Must be globally unique
            ),
        )

        # Admin group
        cognito.CfnUserPoolGroup(
            self,
            "AdminGroup",
            user_pool_id=self.user_pool.user_pool_id,
            group_name="admin",
            description="Administrators with full access",
        )

        # Community managers group
        cognito.CfnUserPoolGroup(
            self,
            "ManagerGroup",
            user_pool_id=self.user_pool.user_pool_id,
            group_name="community-manager",
            description="Community managers who can post announcements",
        )

        # Outputs
        CfnOutput(
            self,
            "UserPoolId",
            value=self.user_pool.user_pool_id,
            export_name="OmnichannelUserPoolId",
        )

        CfnOutput(
            self,
            "UserPoolClientId",
            value=self.user_pool_client.user_pool_client_id,
            export_name="OmnichannelUserPoolClientId",
        )

        CfnOutput(
            self,
            "UserPoolDomain",
            value=self.user_pool_domain.domain_name,
            export_name="OmnichannelUserPoolDomain",
        )

        CfnOutput(
            self,
            "CognitoRegion",
            value=self.region,
            export_name="OmnichannelCognitoRegion",
        )
