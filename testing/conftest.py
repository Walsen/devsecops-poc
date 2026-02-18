"""Pytest configuration for penetration testing."""
import json
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
import docker
import pytest


# ---------------------------------------------------------------------------
# Cognito auth helpers
# ---------------------------------------------------------------------------

def get_cognito_config() -> dict[str, str]:
    """Get Cognito config from CloudFormation outputs."""
    try:
        cf = boto3.client("cloudformation", region_name="us-east-1")
        response = cf.describe_stacks(StackName="AuthStack")
        outputs = {o["OutputKey"]: o["OutputValue"] for o in response["Stacks"][0]["Outputs"]}
        return {
            "user_pool_id": outputs["UserPoolId"],
            "client_id": outputs["UserPoolClientId"],
            "region": outputs.get("CognitoRegion", "us-east-1"),
        }
    except Exception as e:
        pytest.skip(f"Cannot get Cognito config: {e}")


def create_test_user(cognito_client, user_pool_id: str, username: str, email: str) -> str:
    """Create a temporary Cognito test user and return the password."""
    password = f"Test!{secrets.token_hex(8)}Aa1"
    try:
        cognito_client.admin_create_user(
            UserPoolId=user_pool_id,
            Username=username,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
            ],
            TemporaryPassword=password,
            MessageAction="SUPPRESS",
        )
    except cognito_client.exceptions.UsernameExistsException:
        # User exists — try to reset password; if that fails (e.g. stale user
        # created with a different username format), delete and recreate.
        try:
            cognito_client.admin_set_user_password(
                UserPoolId=user_pool_id,
                Username=username,
                Password=password,
                Permanent=True,
            )
            return password
        except cognito_client.exceptions.UserNotFoundException:
            # Stale user with email-format username — delete and recreate
            try:
                cognito_client.admin_delete_user(UserPoolId=user_pool_id, Username=email)
            except Exception:
                pass
            cognito_client.admin_create_user(
                UserPoolId=user_pool_id,
                Username=username,
                UserAttributes=[
                    {"Name": "email", "Value": email},
                    {"Name": "email_verified", "Value": "true"},
                ],
                TemporaryPassword=password,
                MessageAction="SUPPRESS",
            )

    # Set permanent password (skip force-change-password challenge)
    cognito_client.admin_set_user_password(
        UserPoolId=user_pool_id,
        Username=username,
        Password=password,
        Permanent=True,
    )
    return password


def get_auth_token(cognito_client, user_pool_id: str, client_id: str, email: str, password: str) -> str:
    """Authenticate a user and return the access token."""
    response = cognito_client.initiate_auth(
        ClientId=client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": email, "PASSWORD": password},
    )
    return response["AuthenticationResult"]["AccessToken"]


def delete_test_user(cognito_client, user_pool_id: str, email: str) -> None:
    """Delete a test user (cleanup)."""
    try:
        cognito_client.admin_delete_user(UserPoolId=user_pool_id, Username=email)
    except Exception:
        pass


@pytest.fixture(scope="session")
def cognito_config():
    """Cognito User Pool configuration."""
    return get_cognito_config()


@pytest.fixture(scope="session")
def cognito_client():
    """Cognito IDP client."""
    return boto3.client("cognito-idp", region_name="us-east-1")


@pytest.fixture(scope="session")
def test_users(cognito_client, cognito_config):
    """Create two test users and return their tokens. Cleaned up after session."""
    pool_id = cognito_config["user_pool_id"]
    client_id = cognito_config["client_id"]

    user_a_email = "pentest-user-a@test.local"
    user_b_email = "pentest-user-b@test.local"
    user_a_username = "pentest-user-a"
    user_b_username = "pentest-user-b"

    pw_a = create_test_user(cognito_client, pool_id, user_a_username, user_a_email)
    pw_b = create_test_user(cognito_client, pool_id, user_b_username, user_b_email)

    token_a = get_auth_token(cognito_client, pool_id, client_id, user_a_email, pw_a)
    token_b = get_auth_token(cognito_client, pool_id, client_id, user_b_email, pw_b)

    yield {
        "user_a": {"email": user_a_email, "token": token_a},
        "user_b": {"email": user_b_email, "token": token_b},
    }

    # Cleanup
    delete_test_user(cognito_client, pool_id, user_a_username)
    delete_test_user(cognito_client, pool_id, user_b_username)


def fetch_csrf_token(kali_exec_fn, target_url: str) -> str:
    """GET a page to obtain a CSRF cookie, return the token value."""
    _, output = kali_exec_fn(
        f"curl -s -D - {target_url}/api/v1/certifications/types/ -o /dev/null"
    )
    for line in output.splitlines():
        if "csrf_token=" in line.lower():
            part = line.split("csrf_token=", 1)[1]
            return part.split(";")[0].strip()
    return ""


def get_alb_url() -> str:
    """Get ALB URL from CloudFormation or fallback to localhost."""
    try:
        cf = boto3.client("cloudformation", region_name="us-east-1")
        response = cf.describe_stacks(StackName="ComputeStack")
        outputs = response["Stacks"][0]["Outputs"]
        alb_dns = next(o["OutputValue"] for o in outputs if o["OutputKey"] == "AlbDnsName")
        return f"http://{alb_dns}"
    except Exception:
        return "http://localhost"


@pytest.fixture(scope="session")
def target_url():
    """Target URL for testing."""
    return get_alb_url()


@pytest.fixture(scope="session")
def docker_client():
    """Docker client."""
    return docker.from_env()


@pytest.fixture(scope="session")
def kali_container(docker_client):
    """Ensure Kali container is running."""
    container_name = "kali-pentest"
    
    try:
        container = docker_client.containers.get(container_name)
        if container.status != "running":
            container.start()
    except docker.errors.NotFound:
        container = docker_client.containers.run(
            "kali-pentest",
            name=container_name,
            network_mode="host",
            detach=True,
        )
        time.sleep(2)
    
    yield container


@pytest.fixture
def kali_exec(kali_container):
    """Execute commands in Kali container."""
    def _exec(cmd: str | list[str]) -> tuple[int, str]:
        if isinstance(cmd, str):
            cmd = ["sh", "-c", cmd]
        
        exit_code, output = kali_container.exec_run(cmd)
        return exit_code, output.decode("utf-8")
    
    return _exec


@pytest.fixture
def csrf_token(kali_exec, target_url):
    """Fetch a valid CSRF token from the API."""
    token = fetch_csrf_token(kali_exec, target_url)
    if not token:
        pytest.skip("Could not obtain CSRF token from API")
    return token


@pytest.fixture
def cloudwatch_logs():
    """CloudWatch Logs client with helper methods."""
    client = boto3.client("logs", region_name="us-east-1")
    skip_cloudwatch = os.getenv("SKIP_CLOUDWATCH") == "1"
    
    class CloudWatchHelper:
        def __init__(self, client, skip):
            self.client = client
            self.log_group = "/ecs/secure-api/api"
            self.waf_log_group = "aws-waf-logs-alb"
            self.skip = skip
        
        def query_logs(self, filter_pattern: str, minutes_back: int = 5, log_group: str = None) -> list[dict[str, Any]]:
            """Query logs with a filter pattern."""
            log_group = log_group or self.log_group
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(minutes=minutes_back)
            
            query = f"""
            fields @timestamp, @message
            | filter @message like /{filter_pattern}/
            | sort @timestamp desc
            | limit 20
            """
            
            response = self.client.start_query(
                logGroupName=log_group,
                startTime=int(start_time.timestamp()),
                endTime=int(end_time.timestamp()),
                queryString=query,
            )
            
            query_id = response["queryId"]
            
            for _ in range(30):
                result = self.client.get_query_results(queryId=query_id)
                if result["status"] == "Complete":
                    return result["results"]
                time.sleep(1)
            
            return []
        
        def verify_request(self, path: str, status_code: int = None) -> bool:
            """Verify a request was logged."""
            if self.skip:
                return True  # Skip verification for speed
            
            logs = self.query_logs(path)
            if not logs:
                return False
            
            if status_code:
                return any(str(status_code) in str(log) for log in logs)
            
            return True
        
        def verify_waf_block(self, uri_pattern: str = None) -> bool:
            """Verify WAF blocked a request."""
            if self.skip:
                return True  # Skip verification for speed
            
            # Use proper WAF logs query structure
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(minutes=10)  # Look back 10 minutes
            
            query = """
            fields @timestamp, action, httpRequest.uri, httpRequest.args
            | filter action = "BLOCK"
            | sort @timestamp desc
            | limit 10
            """
            
            try:
                response = self.client.start_query(
                    logGroupName=self.waf_log_group,
                    startTime=int(start_time.timestamp()),
                    endTime=int(end_time.timestamp()),
                    queryString=query,
                )
                
                query_id = response["queryId"]
                
                for _ in range(30):
                    result = self.client.get_query_results(queryId=query_id)
                    if result["status"] == "Complete":
                        logs = result["results"]
                        break
                    time.sleep(1)
                else:
                    return False  # Query timeout
                
                if not logs:
                    return False
                
                if uri_pattern:
                    return any(uri_pattern in str(log) for log in logs)
                
                return True
                
            except Exception as e:
                print(f"WAF log verification failed: {e}")
                return False
    
    return CloudWatchHelper(client, skip_cloudwatch)


@pytest.fixture
def cloudwatch_metrics():
    """CloudWatch Metrics client with helper methods."""
    client = boto3.client("cloudwatch", region_name="us-east-1")
    
    class MetricsHelper:
        def __init__(self, client):
            self.client = client
        
        def get_metric_data(self, metric_name: str, namespace: str = "SecureApi", minutes_back: int = 5) -> list[float]:
            """Get metric data points."""
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(minutes=minutes_back)
            
            response = self.client.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                StartTime=start_time,
                EndTime=end_time,
                Period=60,
                Statistics=["Sum", "Average"],
            )
            
            return [dp["Sum"] if "Sum" in dp else dp["Average"] for dp in response["Datapoints"]]
        
        def verify_metric_increase(self, metric_name: str, namespace: str = "SecureApi") -> bool:
            """Verify metric increased (indicating activity)."""
            data = self.get_metric_data(metric_name, namespace)
            return len(data) > 0 and any(v > 0 for v in data)
    
    return MetricsHelper(client)
