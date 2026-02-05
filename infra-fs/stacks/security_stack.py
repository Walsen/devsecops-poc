"""Security Stack - WAF, GuardDuty, and Security Hub for serverless."""

from aws_cdk import (
    Stack,
)
from aws_cdk import (
    aws_guardduty as guardduty,
)
from aws_cdk import (
    aws_securityhub as securityhub,
)
from aws_cdk import (
    aws_wafv2 as wafv2,
)
from constructs import Construct


class SecurityStack(Stack):
    """Security services: WAF for API Gateway, GuardDuty, Security Hub."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        api_gateway_arn: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # WAF Web ACL for API Gateway
        self.web_acl = wafv2.CfnWebACL(
            self,
            "ApiWebAcl",
            name="omnichannel-api-waf",
            scope="REGIONAL",
            default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="omnichannel-api-waf",
                sampled_requests_enabled=True,
            ),
            rules=[
                # AWS Managed Rules - Common Rule Set
                wafv2.CfnWebACL.RuleProperty(
                    name="AWSManagedRulesCommonRuleSet",
                    priority=1,
                    override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                            vendor_name="AWS",
                            name="AWSManagedRulesCommonRuleSet",
                        )
                    ),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="AWSManagedRulesCommonRuleSet",
                        sampled_requests_enabled=True,
                    ),
                ),
                # AWS Managed Rules - Known Bad Inputs
                wafv2.CfnWebACL.RuleProperty(
                    name="AWSManagedRulesKnownBadInputsRuleSet",
                    priority=2,
                    override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                            vendor_name="AWS",
                            name="AWSManagedRulesKnownBadInputsRuleSet",
                        )
                    ),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="AWSManagedRulesKnownBadInputsRuleSet",
                        sampled_requests_enabled=True,
                    ),
                ),
                # Rate limiting
                wafv2.CfnWebACL.RuleProperty(
                    name="RateLimitRule",
                    priority=3,
                    action=wafv2.CfnWebACL.RuleActionProperty(block={}),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                            limit=2000,
                            aggregate_key_type="IP",
                        )
                    ),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="RateLimitRule",
                        sampled_requests_enabled=True,
                    ),
                ),
            ],
        )

        # Associate WAF with API Gateway (if ARN provided)
        if api_gateway_arn:
            wafv2.CfnWebACLAssociation(
                self,
                "ApiWafAssociation",
                resource_arn=api_gateway_arn,
                web_acl_arn=self.web_acl.attr_arn,
            )

        # GuardDuty detector
        self.guardduty_detector = guardduty.CfnDetector(
            self,
            "GuardDutyDetector",
            enable=True,
            finding_publishing_frequency="FIFTEEN_MINUTES",
            features=[
                guardduty.CfnDetector.CFNFeatureConfigurationProperty(
                    name="S3_DATA_EVENTS",
                    status="ENABLED",
                ),
                guardduty.CfnDetector.CFNFeatureConfigurationProperty(
                    name="LAMBDA_NETWORK_LOGS",
                    status="ENABLED",
                ),
            ],
        )

        # Security Hub
        self.security_hub = securityhub.CfnHub(
            self,
            "SecurityHub",
            enable_default_standards=True,
        )
