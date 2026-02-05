from aws_cdk import (
    Duration,
    Stack,
)
from aws_cdk import (
    aws_cognito as cognito,
)
from aws_cdk import (
    aws_ec2 as ec2,
)
from aws_cdk import (
    aws_ecs as ecs,
)
from aws_cdk import (
    aws_elasticloadbalancingv2 as elbv2,
)
from aws_cdk import (
    aws_kinesis as kinesis,
)
from aws_cdk import (
    aws_kms as kms,
)
from aws_cdk import (
    aws_logs as logs,
)
from aws_cdk import (
    aws_secretsmanager as secretsmanager,
)
from aws_cdk import (
    aws_wafv2 as wafv2,
)
from constructs import Construct


class ComputeStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        vpc: ec2.Vpc,
        kms_key: kms.Key,
        db_secret: secretsmanager.Secret,
        event_stream: kinesis.Stream,
        service_security_group: ec2.SecurityGroup,
        alb_security_group: ec2.SecurityGroup,
        user_pool: cognito.UserPool,
        user_pool_client: cognito.UserPoolClient,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # Store reference to security groups (created in NetworkStack)
        self.service_security_group = service_security_group

        # ECS Cluster
        self.cluster = ecs.Cluster(
            self,
            "Cluster",
            vpc=vpc,
            container_insights=True,
        )

        # Cloud Map namespace for service discovery
        self.namespace = self.cluster.add_default_cloud_map_namespace(
            name="secure-api.local",
        )

        # Application Load Balancer
        self.alb = elbv2.ApplicationLoadBalancer(
            self,
            "Alb",
            vpc=vpc,
            internet_facing=True,
            security_group=alb_security_group,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )

        # WAF WebACL for ALB (OWASP rules)
        web_acl = self._create_waf_web_acl()
        wafv2.CfnWebACLAssociation(
            self,
            "AlbWafAssociation",
            resource_arn=self.alb.load_balancer_arn,
            web_acl_arn=web_acl.attr_arn,
        )

        # Shared environment variables for all services
        shared_environment = {
            "SERVICE_NAMESPACE": "secure-api.local",
            "API_SERVICE_HOST": "api.secure-api.local",
            "WORKER_SERVICE_HOST": "worker.secure-api.local",
            "SCHEDULER_SERVICE_HOST": "scheduler.secure-api.local",
            "KINESIS_STREAM_NAME": event_stream.stream_name,
            "AUTH_ENABLED": "true",
            "COGNITO_USER_POOL_ID": user_pool.user_pool_id,
            "COGNITO_CLIENT_ID": user_pool_client.user_pool_client_id,
            "COGNITO_REGION": self.region,
        }

        # ============================================================
        # API Service (Sync - handles HTTP requests)
        # ============================================================
        api_task_def = ecs.FargateTaskDefinition(
            self,
            "ApiTaskDef",
            memory_limit_mib=512,
            cpu=256,
        )
        db_secret.grant_read(api_task_def.task_role)
        event_stream.grant_write(api_task_def.task_role)  # API only writes events
        kms_key.grant_decrypt(api_task_def.task_role)

        api_container = api_task_def.add_container(
            "api",
            image=ecs.ContainerImage.from_registry("amazon/amazon-ecs-sample"),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="api",
                log_retention=logs.RetentionDays.ONE_MONTH,
            ),
            environment={
                **shared_environment,
                "SERVICE_NAME": "api",
            },
            secrets={
                "DB_SECRET": ecs.Secret.from_secrets_manager(db_secret),
            },
        )
        api_container.add_port_mappings(ecs.PortMapping(container_port=8080))

        self.api_service = ecs.FargateService(
            self,
            "ApiService",
            cluster=self.cluster,
            task_definition=api_task_def,
            desired_count=1,
            security_groups=[self.service_security_group],
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            cloud_map_options=ecs.CloudMapOptions(name="api"),
        )

        # ============================================================
        # Worker Service (Async - consumes Kinesis, delivers messages)
        # ============================================================
        worker_task_def = ecs.FargateTaskDefinition(
            self,
            "WorkerTaskDef",
            memory_limit_mib=512,
            cpu=256,
        )
        db_secret.grant_read(worker_task_def.task_role)
        event_stream.grant_read(worker_task_def.task_role)  # Worker reads events
        kms_key.grant_decrypt(worker_task_def.task_role)

        worker_container = worker_task_def.add_container(
            "worker",
            image=ecs.ContainerImage.from_registry("amazon/amazon-ecs-sample"),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="worker",
                log_retention=logs.RetentionDays.ONE_MONTH,
            ),
            environment={
                **shared_environment,
                "SERVICE_NAME": "worker",
            },
            secrets={
                "DB_SECRET": ecs.Secret.from_secrets_manager(db_secret),
            },
        )
        worker_container.add_port_mappings(ecs.PortMapping(container_port=8080))

        self.worker_service = ecs.FargateService(
            self,
            "WorkerService",
            cluster=self.cluster,
            task_definition=worker_task_def,
            desired_count=1,
            security_groups=[self.service_security_group],
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            cloud_map_options=ecs.CloudMapOptions(name="worker"),
        )

        # ============================================================
        # Scheduler Service (Cron - triggers scheduled messages)
        # ============================================================
        scheduler_task_def = ecs.FargateTaskDefinition(
            self,
            "SchedulerTaskDef",
            memory_limit_mib=256,
            cpu=256,
        )
        db_secret.grant_read(scheduler_task_def.task_role)
        event_stream.grant_write(scheduler_task_def.task_role)  # Scheduler writes events
        kms_key.grant_decrypt(scheduler_task_def.task_role)

        scheduler_container = scheduler_task_def.add_container(
            "scheduler",
            image=ecs.ContainerImage.from_registry("amazon/amazon-ecs-sample"),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="scheduler",
                log_retention=logs.RetentionDays.ONE_MONTH,
            ),
            environment={
                **shared_environment,
                "SERVICE_NAME": "scheduler",
            },
            secrets={
                "DB_SECRET": ecs.Secret.from_secrets_manager(db_secret),
            },
        )
        scheduler_container.add_port_mappings(ecs.PortMapping(container_port=8080))

        self.scheduler_service = ecs.FargateService(
            self,
            "SchedulerService",
            cluster=self.cluster,
            task_definition=scheduler_task_def,
            desired_count=1,
            security_groups=[self.service_security_group],
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            cloud_map_options=ecs.CloudMapOptions(name="scheduler"),
        )

        # ============================================================
        # ALB Listener - Only API service is exposed externally
        # Dev: Using HTTP for simplicity. For production, use HTTPS with ACM certificate.
        # ============================================================
        listener = self.alb.add_listener(
            "HttpListener",
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            open=True,
        )

        listener.add_targets(
            "ApiTarget",
            port=8080,
            targets=[self.api_service],
            health_check=elbv2.HealthCheck(
                path="/health",
                interval=Duration.seconds(30),
            ),
        )

    def _create_waf_web_acl(self) -> wafv2.CfnWebACL:
        """Create WAF WebACL with OWASP rules."""
        return wafv2.CfnWebACL(
            self,
            "AlbWebAcl",
            default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
            scope="REGIONAL",
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="secure-api-waf",
                sampled_requests_enabled=True,
            ),
            rules=[
                wafv2.CfnWebACL.RuleProperty(
                    name="AWSManagedRulesCommonRuleSet",
                    priority=1,
                    override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                            vendor_name="AWS",
                            name="AWSManagedRulesCommonRuleSet",
                        ),
                    ),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="CommonRuleSet",
                        sampled_requests_enabled=True,
                    ),
                ),
                wafv2.CfnWebACL.RuleProperty(
                    name="AWSManagedRulesKnownBadInputsRuleSet",
                    priority=2,
                    override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                            vendor_name="AWS",
                            name="AWSManagedRulesKnownBadInputsRuleSet",
                        ),
                    ),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="KnownBadInputs",
                        sampled_requests_enabled=True,
                    ),
                ),
                wafv2.CfnWebACL.RuleProperty(
                    name="AWSManagedRulesSQLiRuleSet",
                    priority=3,
                    override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                            vendor_name="AWS",
                            name="AWSManagedRulesSQLiRuleSet",
                        ),
                    ),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="SQLiRuleSet",
                        sampled_requests_enabled=True,
                    ),
                ),
            ],
        )
