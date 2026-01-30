"""FastAPI application for BYOC Platform."""

import json
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException

from api.database import Database, db
from api.models import (
    CustomerDeployment,
    CustomerOnboardRequest,
    DeploymentResponse,
    DeploymentStatus,
)
from api.pulumi_deployments import PulumiDeploymentsClient
from api.settings import settings

app = FastAPI(
    title="Cortex Prod automaton",
    description="Cortex infrastructure deployment api",
    version="1.0.0",
)


def get_pulumi_client() -> PulumiDeploymentsClient:
    """Get Pulumi Deployments client."""
    return PulumiDeploymentsClient(
        organization=settings.pulumi_org,
        access_token=settings.pulumi_access_token,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        github_token=settings.github_token or None
    )


async def run_deployment(
    request: CustomerOnboardRequest,
    database: Database,
) -> None:
    """Background task to run customer deployment.

    Args:
        request: Customer onboarding request
        database: Database instance
    """
    stack_name = f"{request.customer_name}-{request.environment}"

    try:
        client = get_pulumi_client()

        database.update_deployment_status(
            stack_name=stack_name,
            status=DeploymentStatus.IN_PROGRESS,
        )

        try:
            await client.create_stack(
                project_name=settings.pulumi_project,
                stack_name=stack_name,
            )
        except Exception:
            pass

        await client.configure_deployment_settings(
            project_name=settings.pulumi_project,
            stack_name=stack_name,
            request=request,
            repo_url=settings.git_repo_url,
            repo_branch=settings.git_repo_branch,
            repo_dir=settings.git_repo_dir
        )

        result = await client.trigger_deployment(
            project_name=settings.pulumi_project,
            stack_name=stack_name,
            operation="update",
        )

        deployment_id = result.get("id", "")

        database.update_deployment_status(
            stack_name=stack_name,
            status=DeploymentStatus.IN_PROGRESS,
            pulumi_deployment_id=deployment_id,
        )

    except Exception as e:
        database.update_deployment_status(
            stack_name=stack_name,
            status=DeploymentStatus.FAILED,
            error_message=str(e),
        )



@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/api/v1/customers/onboard", response_model=DeploymentResponse)
async def onboard_customer(
    request: CustomerOnboardRequest,
    background_tasks: BackgroundTasks,
) -> DeploymentResponse:
    """Start a new infra - provisions full infrastructure in their AWS account.

    Args:
        request: Customer onboarding configuration
        background_tasks: FastAPI background tasks

    Returns:
        Deployment response with status
    """
    stack_name = f"{request.customer_name}-{request.environment}"

    existing = db.get_deployment(request.customer_name, request.environment)
    if existing:
        if existing.status == DeploymentStatus.IN_PROGRESS:
            raise HTTPException(
                status_code=409,
                detail=f"Deployment {stack_name} is already in progress",
            )
        if existing.status == DeploymentStatus.SUCCEEDED:
            raise HTTPException(
                status_code=409,
                detail=f"Deployment {stack_name} already exists. Use update endpoint to modify.",
            )

    try:
        db.create_deployment(
            customer_name=request.customer_name,
            environment=request.environment,
            aws_region=request.aws_region,
            role_arn=request.role_arn,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    background_tasks.add_task(run_deployment, request, db)

    return DeploymentResponse(
        customer_name=request.customer_name,
        environment=request.environment,
        stack_name=stack_name,
        status=DeploymentStatus.PENDING,
        message="Deployment initiated. Check status endpoint for progress.",
    )


@app.get(
    "/api/v1/customers/{customer_name}/{environment}/status",
    response_model=CustomerDeployment,
)
async def get_deployment_status(
    customer_name: str,
    environment: str = "prod",
) -> CustomerDeployment:
    """Get the current deployment status

    Args:
        customer_name: Customer identifier
        environment: Environment name (default: prod)

    Returns:
        Customer deployment details
    """
    deployment = db.get_deployment(customer_name, environment)
    if not deployment:
        raise HTTPException(
            status_code=404,
            detail=f"Deployment for {customer_name}-{environment} not found",
        )

    if deployment.status == DeploymentStatus.IN_PROGRESS and deployment.pulumi_deployment_id:
        try:
            client = get_pulumi_client()
            status = await client.get_deployment_status(
                project_name=settings.pulumi_project,
                stack_name=deployment.stack_name,
                deployment_id=deployment.pulumi_deployment_id,
            )

            pulumi_status = status.get("status", "")
            stack_name = deployment.stack_name
            if pulumi_status == "succeeded":
                outputs = await client.get_stack_outputs(
                    project_name=settings.pulumi_project,
                    stack_name=stack_name,
                )
                db.update_deployment_status(
                    stack_name=stack_name,
                    status=DeploymentStatus.SUCCEEDED,
                    outputs=json.dumps(outputs),
                )
                updated = db.get_deployment(customer_name, environment)
                if updated:
                    deployment = updated
            elif pulumi_status == "failed":
                db.update_deployment_status(
                    stack_name=stack_name,
                    status=DeploymentStatus.FAILED,
                    error_message=status.get("message", "Deployment failed"),
                )
                updated = db.get_deployment(customer_name, environment)
                if updated:
                    deployment = updated
        except Exception:
            pass

    return CustomerDeployment(
        id=deployment.id,
        customer_name=deployment.customer_name,
        environment=deployment.environment,
        stack_name=deployment.stack_name,
        aws_region=deployment.aws_region,
        role_arn=deployment.role_arn,
        status=deployment.status,
        pulumi_deployment_id=deployment.pulumi_deployment_id,
        outputs=json.loads(deployment.outputs) if deployment.outputs else None,
        error_message=deployment.error_message,
        created_at=deployment.created_at,
        updated_at=deployment.updated_at,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
