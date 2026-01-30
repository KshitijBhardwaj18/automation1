"""Customer configuration schema and loader."""

from dataclasses import dataclass

import pulumi

from api.models import NodeGroupConfig


@dataclass
class CustomerConfig:
    customer_name: str
    environment: str

    customer_role_arn: str
    external_id: pulumi.Output[str]
    aws_region: str

    vpc_cidr: str
    availability_zones: list[str]

    eks_version: str
    eks_mode: str  # "auto" or "managed"
    node_group_config: NodeGroupConfig | None


def load_customer_config() -> CustomerConfig:
    config = pulumi.Config()

    az_config = config.get("availabilityZones")
    if az_config:
        availability_zones = [az.strip() for az in az_config.split(",")]
    else:
        region = config.get("awsRegion") or "us-east-1"
        availability_zones = [f"{region}a", f"{region}b", f"{region}c"]

    eks_mode = config.get("eksMode") or "managed"

    node_group_config = None
    if eks_mode == "managed":
        instance_types_str = config.get("nodeInstanceTypes") or "t3.medium"
        instance_types = [t.strip() for t in instance_types_str.split(",")]

        node_group_config = NodeGroupConfig(
            instance_types=instance_types,
            desired_size=int(config.get("nodeDesiredSize") or "2"),
            min_size=int(config.get("nodeMinSize") or "1"),
            max_size=int(config.get("nodeMaxSize") or "5"),
            disk_size=int(config.get("nodeDiskSize") or "50"),
            capacity_type=config.get("nodeCapacityType") or "ON_DEMAND",
        )

    return CustomerConfig(
        customer_name=config.require("customerName"),
        environment=config.get("environment") or "prod",
        customer_role_arn=config.require("customerRoleArn"),
        external_id=config.require_secret("externalId"),
        aws_region=config.get("awsRegion") or "us-east-1",
        vpc_cidr=config.get("vpcCidr") or "10.0.0.0/16",
        availability_zones=availability_zones,
        eks_version=config.get("eksVersion") or "1.31",
        eks_mode=eks_mode,
        node_group_config=node_group_config,
    )
