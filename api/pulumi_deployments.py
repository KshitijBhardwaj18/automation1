"""Pulumi Deployments API client for triggering deployments."""

from typing import Any

import httpx

from api.models import CustomerOnboardRequest, EksMode

PULUMI_API_BASE = "https://api.pulumi.com"


class PulumiDeploymentsClient:
    """Client for interacting with Pulumi Deployments API."""

    def __init__(
        self,
        organization: str,
        access_token: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        github_token: str | None = None,
    ):
        """Initialize the Pulumi Deployments client.
        Args:
            organization: Pulumi organization name
            access_token: Pulumi access token
            aws_access_key_id: AWS access key ID for deployments
            aws_secret_access_key: AWS secret access key for deployments
        """
        self.organization = organization
        self.access_token = access_token
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.github_token = github_token

        self.headers = {
            "Authorization": f"token {self.access_token}",
            "Content-Type": "application/json",
        }

    async def create_stack(
        self,
        project_name: str,
        stack_name: str,
    ) -> dict[str, Any]:
        """Create a new Pulumi stack.

        Args:
            project_name: Pulumi project name
            stack_name: Stack name to create

        Returns:
            API response
        """
        url = f"{PULUMI_API_BASE}/api/stacks/{self.organization}/{project_name}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=self.headers,
                json={"stackName": stack_name},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def configure_deployment_settings(
        self,
        project_name: str,
        stack_name: str,
        request: CustomerOnboardRequest,
        repo_url: str,
        repo_branch: str = "main",
        repo_dir: str = ".",
    ) -> dict[str, Any]:
        """Configure deployment settings for a stack.

        Args:
            project_name: Pulumi project name
            stack_name: Stack name
            request: Customer onboarding request with configuration
            repo_url: Git repository URL containing Pulumi code
            repo_branch: Git branch to deploy from
            repo_dir: Directory within repo containing Pulumi.yaml

        Returns:
            API response
        """
        url = (
            f"{PULUMI_API_BASE}/api/stacks/{self.organization}/"
            f"{project_name}/{stack_name}/deployments/settings"
        )

        stack_id = f"{self.organization}/{project_name}/{stack_name}"

        pre_run_commands = [
            "pip install -r requirements.txt",
            f"pulumi config set --stack {stack_id} customerName {request.customer_name}",
            f"pulumi config set --stack {stack_id} environment {request.environment}",
            f"pulumi config set --stack {stack_id} customerRoleArn {request.role_arn}",
            f"pulumi config set --stack {stack_id} --secret externalId {request.external_id}",
            f"pulumi config set --stack {stack_id} awsRegion {request.aws_region}",
            f"pulumi config set --stack {stack_id} vpcCidr {request.vpc_cidr}",
            f"pulumi config set --stack {stack_id} eksVersion {request.eks_version}",
            f"pulumi config set --stack {stack_id} eksMode {request.eks_mode.value}",
        ]

        if request.availability_zones:
            az_str = ",".join(request.availability_zones)
            pre_run_commands.append(
                f"pulumi config set --stack {stack_id} availabilityZones {az_str}"
            )

        if request.eks_mode == EksMode.MANAGED:
            ng = request.node_group_config
            if ng:
                instance_types_str = ",".join(ng.instance_types)
                pre_run_commands.extend(
                    [
                        f"pulumi config set --stack {stack_id} nodeInstanceTypes {instance_types_str}",
                        f"pulumi config set --stack {stack_id} nodeDesiredSize {ng.desired_size}",
                        f"pulumi config set --stack {stack_id} nodeMinSize {ng.min_size}",
                        f"pulumi config set --stack {stack_id} nodeMaxSize {ng.max_size}",
                        f"pulumi config set --stack {stack_id} nodeDiskSize {ng.disk_size}",
                        f"pulumi config set --stack {stack_id} nodeCapacityType {ng.capacity_type}",
                    ]
                )
            else:
                pre_run_commands.extend(
                    [
                        f"pulumi config set --stack {stack_id} nodeInstanceTypes t3.medium",
                        f"pulumi config set --stack {stack_id} nodeDesiredSize 2",
                        f"pulumi config set --stack {stack_id} nodeMinSize 1",
                        f"pulumi config set --stack {stack_id} nodeMaxSize 5",
                        f"pulumi config set --stack {stack_id} nodeDiskSize 50",
                        f"pulumi config set --stack {stack_id} nodeCapacityType ON_DEMAND",
                    ]
                )

        source_context: dict[str, Any] = {
            "git": {
                "repoUrl": repo_url,
                "branch": f"refs/heads/{repo_branch}",
                "repoDir": repo_dir,
            }
        }

        if self.github_token:
            source_context["git"]["gitAuth"] = {"accessToken": {"secret": self.github_token}}

        settings = {
            "sourceContext": source_context,
            "operationContext": {
                "preRunCommands": pre_run_commands,
                "environmentVariables": {
                    "AWS_ACCESS_KEY_ID": self.aws_access_key_id,
                    "AWS_SECRET_ACCESS_KEY": {"secret": self.aws_secret_access_key},
                    "AWS_REGION": request.aws_region,
                },
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=self.headers,
                json=settings,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def trigger_deployment(
        self,
        project_name: str,
        stack_name: str,
        operation: str = "update",
        inherit_settings: bool = True,
    ) -> dict[str, Any]:
        """Trigger a Pulumi deployment.

        Args:
            project_name: Pulumi project name
            stack_name: Stack name to deploy
            operation: Pulumi operation (update, preview, refresh, destroy)
            inherit_settings: Whether to use stack deployment settings

        Returns:
            API response with deployment ID
        """
        url = f"{PULUMI_API_BASE}/api/stacks/{self.organization}/{project_name}/{stack_name}/deployments"

        payload = {
            "operation": operation,
            "inheritSettings": inherit_settings,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_deployment_status(
        self,
        project_name: str,
        stack_name: str,
        deployment_id: str,
    ) -> dict[str, Any]:
        """Get the status of a deployment.

        Args:
            project_name: Pulumi project name
            stack_name: Stack name
            deployment_id: Deployment ID to check

        Returns:
            Deployment status
        """
        url = f"{PULUMI_API_BASE}/api/stacks/{self.organization}/{project_name}/{stack_name}/deployments/{deployment_id}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_stack_outputs(
        self,
        project_name: str,
        stack_name: str,
    ) -> dict[str, Any]:
        """Get stack outputs.

        Args:
            project_name: Pulumi project name
            stack_name: Stack name

        Returns:
            Stack outputs
        """
        url = f"{PULUMI_API_BASE}/api/stacks/{self.organization}/{project_name}/{stack_name}/export"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            deployment = data.get("deployment", {})
            resources = deployment.get("resources", [])

            for resource in resources:
                if resource.get("type") == "pulumi:pulumi:Stack":
                    return resource.get("outputs", {})

            return {}

    async def delete_stack(
        self,
        project_name: str,
        stack_name: str,
        force: bool = False,
    ) -> None:
        """Delete a Pulumi stack.

        Args:
            project_name: Pulumi project name
            stack_name: Stack name to delete
            force: Force delete even if resources exist
        """
        url = f"{PULUMI_API_BASE}/api/stacks/{self.organization}/{project_name}/{stack_name}"
        if force:
            url += "?force=true"

        async with httpx.AsyncClient() as client:
            response = await client.delete(
                url,
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
