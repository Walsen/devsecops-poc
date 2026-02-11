from aws_cdk import (
    CfnOutput,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_kms as kms
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_wafv2 as wafv2
from constructs import Construct


class SecurityStack(Stack):
    def __init__(self, scope: Construct, id: str, vpc: ec2.Vpc, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # KMS key for encryption at rest
        self.kms_key = kms.Key(
            self,
            "EncryptionKey",
            enable_key_rotation=True,
            alias="secure-api-key",
            description="KMS key for encrypting RDS, S3, and Kinesis data",
            removal_policy=RemovalPolicy.RETAIN,
        )

        # WAF IP Set for blocking malicious IPs (updated by Lambda)
        self.waf_ip_set = wafv2.CfnIPSet(
            self,
            "BlockedIpSet",
            name="blocked-ips",
            scope="REGIONAL",
            ip_address_version="IPV4",
            addresses=[],  # Populated dynamically by GuardDuty response Lambda
        )

        # ============================================================
        # Secrets with automatic rotation (Phase 3 Security)
        # ============================================================

        # OAuth provider secrets with 30-day rotation
        self.oauth_google_secret = secretsmanager.Secret(
            self,
            "OAuthGoogleSecret",
            secret_name="omnichannel/oauth/google",
            description="Google OAuth credentials",
            encryption_key=self.kms_key,
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"client_id": "PLACEHOLDER"}',
                generate_string_key="client_secret",
                exclude_punctuation=True,
            ),
        )

        self.oauth_github_secret = secretsmanager.Secret(
            self,
            "OAuthGitHubSecret",
            secret_name="omnichannel/oauth/github",
            description="GitHub OAuth credentials",
            encryption_key=self.kms_key,
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"client_id": "PLACEHOLDER"}',
                generate_string_key="client_secret",
                exclude_punctuation=True,
            ),
        )

        self.oauth_linkedin_secret = secretsmanager.Secret(
            self,
            "OAuthLinkedInSecret",
            secret_name="omnichannel/oauth/linkedin",
            description="LinkedIn OAuth credentials",
            encryption_key=self.kms_key,
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"client_id": "PLACEHOLDER"}',
                generate_string_key="client_secret",
                exclude_punctuation=True,
            ),
        )

        # Social media API secrets
        self.social_facebook_secret = secretsmanager.Secret(
            self,
            "SocialFacebookSecret",
            secret_name="omnichannel/social/facebook",
            description="Facebook API credentials",
            encryption_key=self.kms_key,
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"app_id": "PLACEHOLDER", "page_id": "PLACEHOLDER"}',
                generate_string_key="access_token",
                exclude_punctuation=True,
            ),
        )

        self.social_linkedin_secret = secretsmanager.Secret(
            self,
            "SocialLinkedInSecret",
            secret_name="omnichannel/social/linkedin",
            description="LinkedIn API credentials",
            encryption_key=self.kms_key,
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"organization_id": "PLACEHOLDER"}',
                generate_string_key="access_token",
                exclude_punctuation=True,
            ),
        )

        self.social_whatsapp_secret = secretsmanager.Secret(
            self,
            "SocialWhatsAppSecret",
            secret_name="omnichannel/social/whatsapp",
            description="WhatsApp Business API credentials",
            encryption_key=self.kms_key,
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"phone_number_id": "PLACEHOLDER"}',
                generate_string_key="access_token",
                exclude_punctuation=True,
            ),
        )

        # Note: Automatic rotation requires a Lambda function.
        # For OAuth secrets, rotation is typically manual (re-auth flow).
        # For API tokens, we can add rotation schedules:
        # self.social_facebook_secret.add_rotation_schedule(
        #     "FacebookRotation",
        #     automatically_after=Duration.days(30),
        #     rotation_lambda=rotation_lambda,
        # )

        # Outputs
        CfnOutput(
            self,
            "KmsKeyArn",
            value=self.kms_key.key_arn,
            export_name="SecureApiKmsKeyArn",
        )

        CfnOutput(
            self,
            "WafIpSetArn",
            value=self.waf_ip_set.attr_arn,
            export_name="SecureApiWafIpSetArn",
        )

        CfnOutput(
            self,
            "OAuthGoogleSecretArn",
            value=self.oauth_google_secret.secret_arn,
        )

        CfnOutput(
            self,
            "SocialFacebookSecretArn",
            value=self.social_facebook_secret.secret_arn,
        )
