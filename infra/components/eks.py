import pulumi
import pulumi_aws as aws

from infra.config import NodeGroupConfig


class EksCluster(pulumi.ComponentResource):
    """EKS cluster with private endpoint.

    Supports two modes:
    - Auto Mode: AWS manages compute automatically
    - Managed Mode: You define node groups with specific instance types
    """

    def __init__(
        self,
        name: str,
        vpc_id: pulumi.Output[str],
        private_subnet_ids: pulumi.Output[list[str]],
        cluster_role_arn: pulumi.Output[str],
        node_role_arn: pulumi.Output[str],
        eks_version: str,
        eks_mode: str,  # "auto" or "managed"
        node_group_config: NodeGroupConfig | None,
        provider: aws.Provider,
        opts: pulumi.ResourceOptions | None = None,
    ):
        super().__init__("byoc:infrastructure:EksCluster", name, None, opts)

        child_opts = pulumi.ResourceOptions(parent=self, provider=provider)

       
        self.cluster_sg = aws.ec2.SecurityGroup(
            f"{name}-eks-cluster-sg",
            vpc_id=vpc_id,
            description="Security group for EKS cluster control plane",
            ingress=[
                aws.ec2.SecurityGroupIngressArgs(
                    protocol="-1",
                    from_port=0,
                    to_port=0,
                    self=True,
                ),
            ],
            egress=[
                aws.ec2.SecurityGroupEgressArgs(
                    protocol="-1",
                    from_port=0,
                    to_port=0,
                    cidr_blocks=["0.0.0.0/0"],
                ),
            ],
            opts=child_opts,
        )

        cluster_args = {
            "role_arn": cluster_role_arn,
            "version": eks_version,
            "vpc_config": aws.eks.ClusterVpcConfigArgs(
                subnet_ids=private_subnet_ids,
                security_group_ids=[self.cluster_sg.id],
                endpoint_private_access=True, 
                endpoint_public_access=False,   
            ),
        }

        if eks_mode == "auto":
            cluster_args["compute_config"] = aws.eks.ClusterComputeConfigArgs(
                enabled=True,
                node_pools=["general-purpose"],
            )
            cluster_args["storage_config"] = aws.eks.ClusterStorageConfigArgs(
                block_storage=aws.eks.ClusterStorageConfigBlockStorageArgs(
                    enabled=True,
                ),
            )
            cluster_args["kubernetes_network_config"] = aws.eks.ClusterKubernetesNetworkConfigArgs(
                elastic_load_balancing=aws.eks.ClusterKubernetesNetworkConfigElasticLoadBalancingArgs(
                    enabled=True,
                ),
            )

        self.cluster = aws.eks.Cluster(
            f"{name}-eks-cluster",
            **cluster_args,
            opts=child_opts,
        )

       


        if eks_mode == "managed" and node_group_config:

            self.node_group = aws.eks.NodeGroup(
                f"{name}-eks-node-group",
                cluster_name=self.cluster.name,
                node_role_arn=node_role_arn,
                subnet_ids=private_subnet_ids,
                instance_types=node_group_config.instance_types,
                capacity_type=node_group_config.capacity_type,
                disk_size=node_group_config.disk_size,
                scaling_config=aws.eks.NodeGroupScalingConfigArgs(
                    desired_size=node_group_config.desired_size,
                    min_size=node_group_config.min_size,
                    max_size=node_group_config.max_size,
                ),
                opts=pulumi.ResourceOptions(
                    parent=self,
                    provider=provider,
                    depends_on=[self.cluster],
                ),
            )

        self.cluster_name = self.cluster.name
        self.cluster_endpoint = self.cluster.endpoint
        self.cluster_ca_data = self.cluster.certificate_authority.data
        self.cluster_arn = self.cluster.arn
        self.cluster_security_group_id = self.cluster_sg.id

        self.register_outputs({
            "cluster_name": self.cluster_name,
            "cluster_endpoint": self.cluster_endpoint,
            "cluster_arn": self.cluster_arn,
            "eks_mode": eks_mode,
        })