# CRIU Checkpoint/Restore Lab

## Introduction
This lab introduces Checkpoint/Restore (C/R) technology using CRIU - a powerful Linux utility that allows you to freeze running processes and resume them later. You'll learn both the theoretical concepts and gain hands-on experience with practical checkpoint/restore operations.

## Lab Objectives
- Understand the fundamental concepts of checkpoint/restore technology
- Learn how CRIU works internally to capture and restore process state
- Practice checkpointing and restoring a running Python process
- Analyze the files generated during checkpoint operations
- Experience seamless process migration and state preservation

## Why Do We Need C/R?

### AI Training Scenario
Imagine you're training a large neural network that takes 3 days to complete. After 2 days of training, your server crashes due to a power outage. Without C/R, you'd lose all progress and start over. With C/R, you could checkpoint every few hours and resume from the last save point, losing only minimal progress.

### Gaming Server Example
Consider a game server hosting a 6-hour tournament with 1000 players. If the server needs maintenance, traditional approaches would kick everyone out. With C/R, you can checkpoint the entire game state, perform maintenance, and restore the exact game situation - players wouldn't even notice the interruption.



## What is Checkpoint/Restore:

Checkpoint/Restore (C/R) is a technique that allows you to save the complete state of a running process to disk (checkpoint) and later resume it from exactly where it left off (restore). Think of it like the save/load feature in video games, but for any program.

When you checkpoint a process, the system captures:
- Memory contents
- CPU registers
- Open files and network connections
- Process hierarchy and relationships
- Current execution point
<img width="1307" height="842" alt="cr1 drawio" src="https://github.com/user-attachments/assets/91949251-0541-44de-8165-97d7d9c10279" />


## CRIU: The Checkpoint/Restore Tool

**CRIU** (Checkpoint/Restore In Userspace) is a Linux utility that implements C/R functionality. Unlike kernel-based solutions, CRIU works entirely in userspace, making it more portable and easier to use.

### CRIU Checkpointing Process

#### 1. Process Discovery and Freezing
When you run `criu dump -t PID`, CRIU first freezes the target process using Linux's `ptrace()` system call or cgroup freezer. This prevents the process from changing state during checkpointing.

```
Process State: Running → Frozen (via ptrace/cgroup)
```

#### 2. Memory Extraction
CRIU reads the process's memory layout from `/proc/PID/maps` and extracts memory contents:

```bash
# Example memory map entry
7f8b4c000000-7f8b4c021000 rw-p 00000000 00:00 0    [heap]
```

- **Virtual Memory Areas (VMAs)**: Each memory region (code, heap, stack, shared libraries) is identified
- **Page-by-page copying**: Memory contents are read via `/proc/PID/mem` or `process_vm_readv()`
- **Memory optimization**: CRIU can detect shared memory and avoid duplicating identical pages

#### 3. File Descriptors and Resources
CRIU inventories all open resources by examining `/proc/PID/fd/`:

```bash
/proc/1234/fd/0 → /dev/pts/1    (stdin)
/proc/1234/fd/1 → /dev/pts/1    (stdout)
/proc/1234/fd/3 → /tmp/data.txt (open file)
```

For each FD, CRIU saves:
- File path and position (`lseek` offset)
- File flags (read/write mode, append, etc.)
- Socket states (for network connections)

#### 4. CPU State Capture
CRIU extracts CPU registers using `ptrace(PTRACE_GETREGS)`:
- General-purpose registers (RAX, RBX, RCX, etc.)
- Instruction pointer (RIP) - where execution should resume
- Stack pointer (RSP)
- Floating-point state

#### 5. Process Tree and Relationships
CRIU maps the entire process hierarchy:
- Parent-child relationships
- Process groups and sessions
- Signal handlers and pending signals

### CRIU's File Structure
After checkpointing, CRIU creates several files:

```
checkpoint_dir/
├── core-1234.img        # Main process image (registers, IDs)
├── mm-1234.img          # Memory mappings metadata  
├── pages-1.img          # Actual memory pages
├── files.img            # File descriptor table
├── fs-1234.img          # Filesystem info (cwd, root)
└── stats-dump           # Checkpoint statistics
```
<img width="1652" height="872" alt="cr2 drawio" src="https://github.com/user-attachments/assets/4ffd5d32-a0d6-4eb7-961b-d2a8f2798a6a" />

### CRIU Restore Process

During `criu restore`:

1. **Process Creation**: Fork a new process with the same PID (using `clone()` with specific flags)

2. **Memory Reconstruction**: 
   - Create VMAs using `mmap()`
   - Load memory pages from checkpoint files
   - Restore heap, stack, and code segments

3. **Resource Recovery**:
   - Reopen files at exact positions
   - Recreate sockets and network connections
   - Restore signal handlers

4. **CPU State Restoration**: Use `ptrace(PTRACE_SETREGS)` to restore all registers

5. **Resume Execution**: The process continues from the exact instruction where it was checkpointed
<img width="1577" height="683" alt="cr3 drawio" src="https://github.com/user-attachments/assets/34fc325f-183f-48ec-8a28-8e9e26385207" />

### Key Technical Challenges CRIU Solves

- **PID Restoration**: Linux normally assigns PIDs sequentially. CRIU uses `clone()` with `CLONE_NEWPID` to control PID assignment
- **Memory Sharing**: Handles shared memory segments and memory-mapped files correctly
- **Resource Dependencies**: Manages complex relationships between processes, files, and network connections
## Lab Environment Setup: AWS EC2

Before we begin the CRIU demonstration, we'll set up an AWS EC2 instance with the necessary tools pre-installed.

### Step 1: Configure AWS CLI
Configure your AWS credentials:
```bash
aws configure
```
Enter your AWS Access Key ID, Secret Access Key, region (recommended: ap-southeast-1), and output format (json).
<img width="1480" height="546" alt="image" src="https://github.com/user-attachments/assets/12f9fc7b-ea0f-4bc3-b96d-89b8646ddace" />

### Step 2: Generate SSH Key Pair
Create a new key pair for secure access to your EC2 instance:
```bash
aws ec2 create-key-pair --key-name jilan-key-new --query 'KeyMaterial' --output text > jilan-key-new.pem
chmod 400 jilan-key-new.pem
```

### Step 3: Deploy Infrastructure with Pulumi
 Initialize a New Pulumi Project

Pulumi is an Infrastructure-as-Code (IaC) tool used to manage cloud infrastructure. In this tutorial, you'll use Pulumi python to provision the AWS resources required for Database Cluster.
First login to Pulumi by running the command in the terminal. You will require a token to login. You can get the token from the Pulumi website.
```bash
pulumi login
```
after login, create a new directory for your infrastructure code and save the provided Pulumi Python script as `__main__.py`. Then deploy:
```bash
mkdir criu-pulumi
cd criu-pulumi

pulumi new aws-python
```
Replace the generated __main__.py with the provided Pulumi code in the REPO
```python
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
pulumi.export("ssh_connection", pulumi.Output.concat("ssh -i jilan-key-new.pem ubuntu@", ec2_instance.public_ip))
```
Build the aws Infrastructure:
```bash
pulumi up --yes
cd ..
```
<img width="1480" height="546" alt="image" src="https://github.com/user-attachments/assets/9e5e5eb0-7bbb-49e8-95ef-8a93e5d92a4f" />


### Step 4: Connect to EC2 Instance
Once deployment completes successfully, connect to your instance using the public IP from Pulumi output:
```bash
ssh -i jilan-key-new.pem ubuntu@<EC2_PUBLIC_IP>
```

Verify the installation:
```bash
criu --version
criu check
```

The `criu check` command will validate that your system supports all necessary features for checkpoint/restore operations.

## Hands-On Demo: Python Counter with CRIU
Now that your environment is ready, let's demonstrate CRIU's capabilities with a simple Python counter program.
### Step 1: Create the Counter Program

Create `counter.py` using Nano editor:

```python
#!/usr/bin/env python3
import time
import os

def main():
    counter = 0
    print(f"Counter started with PID: {os.getpid()}")
    
    while True:
        print(f"Counter: {counter}")
        counter += 1
        time.sleep(2)

if __name__ == "__main__":
    main()
```

### Step 2: Run and Checkpoint

1. **Make the file executable and start the program:**
```bash
chmod +x counter.py
./counter.py &
```
Note the PID (let's say it's 12345).
<img width="1480" height="546" alt="image" src="https://github.com/user-attachments/assets/1d58b806-de5f-4554-818a-b9faed9c53e5" />

2. **Open a new terminal window/tab side by side** to perform checkpoint and restore operations while keeping the original terminal for monitoring the counter output.

3. **In the new terminal, SSH into the EC2 again, then checkpoint:**
```bash
ssh -i jilan-key-new.pem ubuntu@<EC2_PUBLIC_IP>
```
```bash
# Create directory for checkpoint files
mkdir checkpoint_dir

# Checkpoint the process (replace 12345 with actual PID)
sudo criu dump -t 12345 -D checkpoint_dir -v4 --shell-job
```

The process will be frozen and its state saved to `checkpoint_dir`.

<img width="1480" height="546" alt="image" src="https://github.com/user-attachments/assets/0cbeb340-eeb3-4194-a0cf-743564298890" />

### Step 3: Examine Checkpoint Files

Explore the generated checkpoint files to understand what CRIU captured:
```bash
ls -la checkpoint_dir/
file checkpoint_dir/*
```

You'll see various `.img` files containing different aspects of the process state.
<img width="1480" height="546" alt="image" src="https://github.com/user-attachments/assets/4105b00d-2ef7-46e2-8edc-b77af52d3e9a" />

### Step 4: Restore the Process

To restore the process:
```bash
# Restore from checkpoint
sudo criu restore -D checkpoint_dir -v4 --shell-job
```

The counter will resume from exactly where it was checkpointed, continuing with the same count value!
<img width="1480" height="546" alt="image" src="https://github.com/user-attachments/assets/db7d4ef9-54e9-42dd-bf00-fb52d77c4267" />

### What Happened?

1. **Checkpoint**: CRIU captured the entire process state, including the `counter` variable's value (stored in Python's memory), program position, and all memory contents.

2. **Restore**: CRIU recreated the process with identical state, resuming execution from the exact same point in the `while` loop.

## Key Benefits

- **Fault Tolerance**: Recover from crashes without losing work
- **Migration**: Move processes between machines
- **Debugging**: Reproduce exact program states
- **Resource Management**: Pause long-running jobs during peak hours
- **Cost Optimization**: Leverage cheaper cloud resources through seamless migration

## Limitations to Consider

- Not all programs can be checkpointed (those with hardware dependencies, active network connections)
- Requires root privileges
- Checkpoint files can be large
- Some restoration scenarios need careful environment matching

This simple demo shows C/R's power: the ability to freeze time for a process and resume it later, making computing more resilient, flexible, and cost-effective.
