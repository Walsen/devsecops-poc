from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_ecr as ecr
from constructs import Construct


class RegistryStack(Stack):
    """ECR repositories for container images.

    Deployed independently before container builds so that
    build-and-push jobs have somewhere to push to.
    """

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        service_names = ["api", "worker", "scheduler"]

        self.repositories: dict[str, ecr.Repository] = {}
        for name in service_names:
            self.repositories[name] = ecr.Repository(
                self,
                f"{name.capitalize()}Repo",
                repository_name=name,
                removal_policy=RemovalPolicy.DESTROY,
                empty_on_delete=True,
                lifecycle_rules=[
                    ecr.LifecycleRule(
                        description="Keep last 10 images",
                        max_image_count=10,
                    ),
                ],
            )
