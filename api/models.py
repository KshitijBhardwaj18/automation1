"""Pydantic models for API requests and responses."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

class DeploymentStatus(str, Enum):
    """Status of a customer deployment."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DESTROYING = "destroying"
    DESTROYED = "destroyed"

class EksMode(str, Enum):
    """EKS compute mode."""

    AUTO = "auto"        
    MANAGED = "managed"

class NodeGroupConfig(BaseModel):
    """Configuration for managed node group (only used when eks_mode=managed)."""

    instance_types: list[str] = Field(
        default=["t3.medium"],
        description="EC2 instance types for worker nodes",
    )
    desired_size: int = Field(
        default=2,
        description="Desired number of nodes",
        ge=1,
        le=100,
    )
    min_size: int = Field(
        default=1,
        description="Minimum number of nodes",
        ge=1,
        le=100,
    )
    max_size: int = Field(
        default=5,
        description="Maximum number of nodes",
        ge=1,
        le=100,
    )
    disk_size: int = Field(
        default=50,
        description="Disk size in GB for each node",
        ge=20,
        le=1000,
    )
    capacity_type: str = Field(
        default="ON_DEMAND",
        description="Capacity type: ON_DEMAND or SPOT",
        pattern=r"^(ON_DEMAND|SPOT)$",
    )


class CustomerOnboardRequest(BaseModel):
    """Request to onboard a new customer."""

    customer_name: str = Field(
        ...,
        description="Unique customer identifier (used in stack name)",
        pattern=r"^[a-z0-9-]+$",
        min_length=3,
        max_length=50,
    )
    environment: str = Field(
        default="prod",
        description="Environment name (dev/staging/prod)",
        pattern=r"^[a-z0-9-]+$",
    )

    role_arn: str = Field(
        ...,
        description="Customer's IAM role ARN for cross-account access",
        pattern=r"^arn:aws:iam::\d{12}:role/.+$",
    )
    external_id: str = Field(
        ...,
        description="External ID for secure role assumption",
        min_length=10,
    )

    aws_region: str = Field(
        default="us-east-1",
        description="AWS region for deployment",
    )

    vpc_cidr: str = Field(
        default="10.0.0.0/16",
        description="VPC CIDR block",
    )

    availability_zones: Optional[list[str]] = Field(
        default=None,
        description="Availability zones (defaults to 3 AZs in the region)",
    )

    eks_version: str = Field(
        default="1.31",
        description="EKS Kubernetes version",
    )

    eks_mode: EksMode = Field(
        default=EksMode.MANAGED,
        description="EKS compute mode: 'auto' (AWS manages) or 'managed' (you configure node groups)",
    )
    
    node_group_config: Optional[NodeGroupConfig] = Field(
        default=None,
        description="Node group configuration (only used when eks_mode=managed)",
    )



class CustomerDeployment(BaseModel):
    """Customer deployment record."""

    id: int
    customer_name: str
    environment: str
    stack_name: str
    aws_region: str
    role_arn: str
    status: DeploymentStatus
    pulumi_deployment_id: Optional[str] = None
    outputs: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeploymentResponse(BaseModel):
    """Response for deployment operations."""
    customer_name: str
    environment: str
    stack_name: str
    status: DeploymentStatus
    message: str
    deployment_id: Optional[str] = None


