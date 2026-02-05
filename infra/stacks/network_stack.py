from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
)
from constructs import Construct


class NetworkStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # VPC with public and private subnets across 2 AZs
        # Dev: Single NAT gateway to reduce costs
        self.vpc = ec2.Vpc(
            self, "SecureApiVpc",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Isolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
        )

        # VPC Flow Logs
        self.vpc.add_flow_log(
            "FlowLog",
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(),
            traffic_type=ec2.FlowLogTrafficType.ALL,
        )

        # VPC Endpoints for AWS services (keeps traffic private)
        self.vpc.add_gateway_endpoint(
            "S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
        )

        # Dev: Skip interface endpoints to reduce costs (~$36/month savings)
        # Traffic will go through NAT gateway instead
        # Uncomment for production:
        # self.vpc.add_interface_endpoint(
        #     "SecretsManagerEndpoint",
        #     service=ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
        # )
        # self.vpc.add_interface_endpoint(
        #     "EcrEndpoint",
        #     service=ec2.InterfaceVpcEndpointAwsService.ECR,
        # )
