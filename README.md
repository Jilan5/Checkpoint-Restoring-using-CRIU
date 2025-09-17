# Checkpoint/Restore (C/R): Saving and Resuming Program State

## What is Checkpoint/Restore:

Checkpoint/Restore (C/R) is a technique that allows you to save the complete state of a running process to disk (checkpoint) and later resume it from exactly where it left off (restore). Think of it like the save/load feature in video games, but for any program.

When you checkpoint a process, the system captures:
- Memory contents
- CPU registers
- Open files and network connections
- Process hierarchy and relationships
- Current execution point
<img width="1222" height="782" alt="CR 2 drawio" src="https://github.com/user-attachments/assets/1ac693f2-acf7-4a97-b1a0-fa7ab8d53d17" />

## Why Do We Need C/R?

### AI Training Scenario
Imagine you're training a large neural network that takes 3 days to complete. After 2 days of training, your server crashes due to a power outage. Without C/R, you'd lose all progress and start over. With C/R, you could checkpoint every few hours and resume from the last save point, losing only minimal progress.

### Gaming Server Example
Consider a game server hosting a 6-hour tournament with 1000 players. If the server needs maintenance, traditional approaches would kick everyone out. With C/R, you can checkpoint the entire game state, perform maintenance, and restore the exact game situation - players wouldn't even notice the interruption.

### Server Crash Recovery in Cloud Computing
In cloud environments, server crashes can result in significant data loss and downtime. Imagine you're running a critical web application processing thousands of user transactions. During peak traffic, your server suddenly crashes due to hardware failure or power outage. Without C/R, you'd lose all in-memory session data, active connections, and processing state - forcing users to restart their workflows and potentially losing business.

With C/R, you can:
- **Automatic Recovery**: Periodically checkpoint your application state and automatically restore it on a backup server when the primary fails
- **Seamless Failover**: Users experience minimal disruption as the application resumes exactly where it left off, maintaining session data and transaction states  
- **Data Preservation**: All in-memory caches, user sessions, and processing queues are preserved across server failures

## CRIU: The Checkpoint/Restore Tool

**CRIU** (Checkpoint/Restore In Userspace) is a Linux utility that implements C/R functionality. Unlike kernel-based solutions, CRIU works entirely in userspace, making it more portable and easier to use.

### How CRIU Works Internally

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
<img width="1081" height="721" alt="CRIU internals drawio" src="https://github.com/user-attachments/assets/57b38392-6304-4047-9e11-ced4eeb07f2c" />

### Restoration Process

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
<img width="821" height="551" alt="criu restore drawio" src="https://github.com/user-attachments/assets/9e150c77-d94a-4dc3-9362-024328b241b3" />

### Key Technical Challenges CRIU Solves

- **PID Restoration**: Linux normally assigns PIDs sequentially. CRIU uses `clone()` with `CLONE_NEWPID` to control PID assignment
- **Memory Sharing**: Handles shared memory segments and memory-mapped files correctly
- **Resource Dependencies**: Manages complex relationships between processes, files, and network connections

## Simple Demo: Python Counter with CRIU

### Prerequisites
First, install CRIU:
```bash
# Ubuntu/Debian
# Install CRIU
add-apt-repository ppa:criu/ppa -y
apt update -y
apt install criu -y

# Verify installation
criu --version
criu check
```

### Step 1: Create the Counter Program

Create `counter.py`:

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
<img width="1465" height="523" alt="image" src="https://github.com/user-attachments/assets/b3f3db70-db44-4460-b7bb-1335196cf0aa" />

2. **Open a new terminal window/tab side by side** to perform checkpoint and restore operations while keeping the original terminal for monitoring the counter output.

3. **In the new terminal, let the counter run for a few iterations, then checkpoint:**
```bash
# Create directory for checkpoint files
mkdir checkpoint_dir

# Checkpoint the process (replace 12345 with actual PID)
sudo criu dump -t 12345 -D checkpoint_dir -v4 --shell-job
```

The process will be frozen and its state saved to `checkpoint_dir`.

<img width="1465" height="523" alt="image" src="https://github.com/user-attachments/assets/676e58bf-6940-4030-846d-855d8c7f3779" />


### Step 3: Restore the Process

To restore the process:
```bash
# Restore from checkpoint
sudo criu restore -D checkpoint_dir -v4 --shell-job
```

The counter will resume from exactly where it was checkpointed, continuing with the same count value!

<img width="1465" height="582" alt="image" src="https://github.com/user-attachments/assets/c933af45-59ae-45ea-9815-a9df2d77f6d3" />

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
