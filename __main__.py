import pulumi
import pulumi_aws as aws

# Configure AWS provider (region will be set via pulumi config or environment)
# You can set it with: pulumi config set aws:region ap-southeast-1

# Use existing key pair (manually created)
# Key pair should be created with: aws ec2 create-key-pair --key-name jilan-key --query 'KeyMaterial' --output text > jilan-key.pem
key_name = "jilan-key-new"

# Userdata script embedded within Python
userdata_script = """#!/bin/bash
set -e

# Log start
echo "Starting userdata script at $(date)" >> /var/log/userdata.log

# Update system
apt update -y

# Install software-properties-common for add-apt-repository
apt install -y software-properties-common

# Install CRIU
add-apt-repository ppa:criu/ppa -y
apt update -y
apt install criu -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Add user to docker group
usermod -aG docker ubuntu

# Enable Docker experimental features
mkdir -p /etc/docker
echo '{"experimental": true}' > /etc/docker/daemon.json

# Start and enable Docker
systemctl enable docker
systemctl start docker
systemctl restart docker

# Log completion
echo "Userdata script completed at $(date)" >> /var/log/userdata.log
"""

# Create VPC
vpc = aws.ec2.Vpc("my-vpc",
    cidr_block="10.0.0.0/16",
    enable_dns_support=True,
    enable_dns_hostnames=True,
    tags={
        "Name": "my-vpc"
    }
)

# Create Public Subnet
public_subnet = aws.ec2.Subnet("public-subnet",
    vpc_id=vpc.id,
    cidr_block="10.0.1.0/24",
    availability_zone="ap-southeast-1a",
    map_public_ip_on_launch=True,
    tags={
        "Name": "public-subnet"
    }
)

# Create Internet Gateway
igw = aws.ec2.InternetGateway("my-internet-gateway",
    vpc_id=vpc.id,
    tags={
        "Name": "my-internet-gateway"
    }
)

# Create Route Table for Public Subnet
public_rt = aws.ec2.RouteTable("public-route-table",
    vpc_id=vpc.id,
    routes=[
        aws.ec2.RouteTableRouteArgs(
            cidr_block="0.0.0.0/0",
            gateway_id=igw.id,
        )
    ],
    tags={
        "Name": "public-route-table"
    }
)

# Associate Route Table with Public Subnet
public_association = aws.ec2.RouteTableAssociation("public-association",
    subnet_id=public_subnet.id,
    route_table_id=public_rt.id
)

# Create Security Group for EC2 Instance
ec2_sg = aws.ec2.SecurityGroup("ec2-security-group",
    name_prefix="ec2-sg-",
    vpc_id=vpc.id,
    description="Security group for EC2 instance",
    ingress=[
        # Allow SSH (Port 22) from anywhere
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=22,
            to_port=22,
            cidr_blocks=["0.0.0.0/0"],
        ),
        # Allow HTTP (Port 80) from anywhere
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=80,
            to_port=80,
            cidr_blocks=["0.0.0.0/0"],
        ),
        # Allow HTTPS (Port 443) from anywhere
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=443,
            to_port=443,
            cidr_blocks=["0.0.0.0/0"],
        ),
        # Allow Application Traffic (Port 8000)
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=8000,
            to_port=8000,
            cidr_blocks=["0.0.0.0/0"],  # Modify for specific IPs if needed
        ),
    ],
    egress=[
        # Allow all outbound traffic
        aws.ec2.SecurityGroupEgressArgs(
            protocol="-1",
            from_port=0,
            to_port=0,
            cidr_blocks=["0.0.0.0/0"],
        )
    ],
    tags={
        "Name": "ec2-security-group"
    }
)

# Create EC2 Instance in Public Subnet
ec2_instance = aws.ec2.Instance("criu-docker-instance",
    ami="ami-0672fd5b9210aa093",  # Ubuntu 22.04 LTS
    instance_type="t2.micro",
    subnet_id=public_subnet.id,
    vpc_security_group_ids=[ec2_sg.id],
    associate_public_ip_address=True,
    key_name=key_name,
    user_data=userdata_script,
    tags={
        "Name": "criu-docker-instance"
    }
)

# Export outputs
pulumi.export("ec2_public_ip", ec2_instance.public_ip)
pulumi.export("ssh_connection", pulumi.Output.concat("ssh -i jilan-key.pem ubuntu@", ec2_instance.public_ip))