"""Pydantic models for API requests and responses."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


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


# -----------------------------------------------------------------------------
# Customer Configuration Models
# -----------------------------------------------------------------------------


class CustomerConfigCreate(BaseModel):
    """Request model for creating a customer configuration."""

    customer_id: str = Field(
        ...,
        description="Unique customer identifier",
        pattern=r"^[a-z0-9-]+$",
        min_length=3,
        max_length=50,
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
        description="EKS compute mode: 'auto' or 'managed'",
    )
    node_group_config: Optional[NodeGroupConfig] = Field(
        default=None,
        description="Node group configuration (only used when eks_mode=managed)",
    )

    @field_validator("vpc_cidr")
    @classmethod
    def validate_vpc_cidr(cls, v: str) -> str:
        """Validate VPC CIDR format."""
        import ipaddress

        try:
            network = ipaddress.ip_network(v, strict=False)
            # Ensure it's a reasonable VPC size (between /16 and /24)
            if network.prefixlen < 16 or network.prefixlen > 24:
                raise ValueError("VPC CIDR prefix must be between /16 and /24")
        except ValueError as e:
            raise ValueError(f"Invalid VPC CIDR: {e}") from e
        return v

    @field_validator("aws_region")
    @classmethod
    def validate_aws_region(cls, v: str) -> str:
        """Validate AWS region format."""
        valid_regions = [
            "us-east-1",
            "us-east-2",
            "us-west-1",
            "us-west-2",
            "eu-west-1",
            "eu-west-2",
            "eu-west-3",
            "eu-central-1",
            "eu-north-1",
            "ap-south-1",
            "ap-southeast-1",
            "ap-southeast-2",
            "ap-northeast-1",
            "ap-northeast-2",
            "ap-northeast-3",
            "sa-east-1",
            "ca-central-1",
        ]
        if v not in valid_regions:
            raise ValueError(f"Invalid AWS region. Must be one of: {valid_regions}")
        return v


class CustomerConfigUpdate(BaseModel):
    """Request model for updating a customer configuration.

    All fields are optional - only provided fields will be updated.
    """

    role_arn: Optional[str] = Field(
        default=None,
        description="Customer's IAM role ARN for cross-account access",
        pattern=r"^arn:aws:iam::\d{12}:role/.+$",
    )
    external_id: Optional[str] = Field(
        default=None,
        description="External ID for secure role assumption",
        min_length=10,
    )
    aws_region: Optional[str] = Field(
        default=None,
        description="AWS region for deployment",
    )
    vpc_cidr: Optional[str] = Field(
        default=None,
        description="VPC CIDR block",
    )
    availability_zones: Optional[list[str]] = Field(
        default=None,
        description="Availability zones",
    )
    eks_version: Optional[str] = Field(
        default=None,
        description="EKS Kubernetes version",
    )
    eks_mode: Optional[EksMode] = Field(
        default=None,
        description="EKS compute mode: 'auto' or 'managed'",
    )
    node_group_config: Optional[NodeGroupConfig] = Field(
        default=None,
        description="Node group configuration",
    )

    @field_validator("vpc_cidr")
    @classmethod
    def validate_vpc_cidr(cls, v: Optional[str]) -> Optional[str]:
        """Validate VPC CIDR format if provided."""
        if v is None:
            return v
        import ipaddress

        try:
            network = ipaddress.ip_network(v, strict=False)
            if network.prefixlen < 16 or network.prefixlen > 24:
                raise ValueError("VPC CIDR prefix must be between /16 and /24")
        except ValueError as e:
            raise ValueError(f"Invalid VPC CIDR: {e}") from e
        return v

    @field_validator("aws_region")
    @classmethod
    def validate_aws_region(cls, v: Optional[str]) -> Optional[str]:
        """Validate AWS region format if provided."""
        if v is None:
            return v
        valid_regions = [
            "us-east-1",
            "us-east-2",
            "us-west-1",
            "us-west-2",
            "eu-west-1",
            "eu-west-2",
            "eu-west-3",
            "eu-central-1",
            "eu-north-1",
            "ap-south-1",
            "ap-southeast-1",
            "ap-southeast-2",
            "ap-northeast-1",
            "ap-northeast-2",
            "ap-northeast-3",
            "sa-east-1",
            "ca-central-1",
        ]
        if v not in valid_regions:
            raise ValueError(f"Invalid AWS region. Must be one of: {valid_regions}")
        return v


class CustomerConfig(BaseModel):
    """Full customer configuration model (stored in file)."""

    customer_id: str = Field(
        ...,
        description="Unique customer identifier",
    )
    role_arn: str = Field(
        ...,
        description="Customer's IAM role ARN for cross-account access",
    )
    external_id: str = Field(
        ...,
        description="External ID for secure role assumption",
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
        description="Availability zones",
    )
    eks_version: str = Field(
        default="1.31",
        description="EKS Kubernetes version",
    )
    eks_mode: EksMode = Field(
        default=EksMode.MANAGED,
        description="EKS compute mode",
    )
    node_group_config: Optional[NodeGroupConfig] = Field(
        default=None,
        description="Node group configuration",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Configuration creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Configuration last update timestamp",
    )

    @classmethod
    def from_create_request(cls, request: CustomerConfigCreate) -> "CustomerConfig":
        """Create a CustomerConfig from a create request.

        Args:
            request: The create request with configuration data

        Returns:
            A new CustomerConfig instance
        """
        now = datetime.now(timezone.utc)
        return cls(
            customer_id=request.customer_id,
            role_arn=request.role_arn,
            external_id=request.external_id,
            aws_region=request.aws_region,
            vpc_cidr=request.vpc_cidr,
            availability_zones=request.availability_zones,
            eks_version=request.eks_version,
            eks_mode=request.eks_mode,
            node_group_config=request.node_group_config,
            created_at=now,
            updated_at=now,
        )

    def apply_update(self, update: CustomerConfigUpdate) -> "CustomerConfig":
        """Apply an update to this configuration.

        Args:
            update: The update request with fields to change

        Returns:
            A new CustomerConfig with updates applied
        """
        update_data = update.model_dump(exclude_unset=True)
        current_data = self.model_dump()
        current_data.update(update_data)
        current_data["updated_at"] = datetime.now(timezone.utc)
        return CustomerConfig.model_validate(current_data)


class CustomerConfigResponse(BaseModel):
    """Response model for customer configuration (hides sensitive fields)."""

    customer_id: str
    role_arn: str
    aws_region: str
    vpc_cidr: str
    availability_zones: Optional[list[str]]
    eks_version: str
    eks_mode: EksMode
    node_group_config: Optional[NodeGroupConfig]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_config(cls, config: CustomerConfig) -> "CustomerConfigResponse":
        """Create a response from a full config (excludes external_id).

        Args:
            config: The full customer configuration

        Returns:
            A response model safe for API responses
        """
        return cls(
            customer_id=config.customer_id,
            role_arn=config.role_arn,
            aws_region=config.aws_region,
            vpc_cidr=config.vpc_cidr,
            availability_zones=config.availability_zones,
            eks_version=config.eks_version,
            eks_mode=config.eks_mode,
            node_group_config=config.node_group_config,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )


class CustomerConfigListResponse(BaseModel):
    """Response model for listing customer configurations."""

    configs: list[CustomerConfigResponse]
    total: int


class DeployRequest(BaseModel):
    """Request model for triggering a deployment."""

    environment: str = Field(
        default="prod",
        description="Environment name (dev/staging/prod)",
        pattern=r"^[a-z0-9-]+$",
    )


class DestroyRequest(BaseModel):
    """Request model for destroying infrastructure."""

    confirm: bool = Field(
        ...,
        description="Must be true to confirm destruction",
    )

    @field_validator("confirm")
    @classmethod
    def validate_confirm(cls, v: bool) -> bool:
        """Ensure confirm is explicitly set to true."""
        if not v:
            raise ValueError("confirm must be true to destroy infrastructure")
        return v
