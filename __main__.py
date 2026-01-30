import pulumi

from infra.components.eks import EksCluster
from infra.components.iam import EksIamRoles
from infra.components.networking import Networking
from infra.config import load_customer_config
from infra.providers import create_customer_aws_provider

config = load_customer_config()

aws_provider = create_customer_aws_provider(config)

networking = Networking(
    name=config.customer_name,
    vpc_cidr=config.vpc_cidr,
    availability_zones=config.availability_zones,
    provider=aws_provider,
)

iam = EksIamRoles(
    name=config.customer_name,
    provider=aws_provider,
    opts=pulumi.ResourceOptions(depends_on=[networking]),
)

eks = EksCluster(
    name=config.customer_name,
    vpc_id=networking.vpc_id,
    private_subnet_ids=networking.private_subnet_ids,
    cluster_role_arn=iam.cluster_role_arn,
    node_role_arn=iam.node_role_arn,
    eks_version=config.eks_version,
    eks_mode=config.eks_mode,
    node_group_config=config.node_group_config,
    provider=aws_provider,
    opts=pulumi.ResourceOptions(depends_on=[iam]),
)

pulumi.export("vpc_id", networking.vpc_id)
pulumi.export("private_subnet_ids", networking.private_subnet_ids)
pulumi.export("public_subnet_ids", networking.public_subnet_ids)

pulumi.export("eks_cluster_role_arn", iam.cluster_role_arn)
pulumi.export("eks_node_role_arn", iam.node_role_arn)
pulumi.export("eks_node_instance_profile_arn", iam.node_instance_profile_arn)

pulumi.export("eks_cluster_name", eks.cluster_name)
pulumi.export("eks_cluster_endpoint", eks.cluster_endpoint)
pulumi.export("eks_mode", config.eks_mode)
