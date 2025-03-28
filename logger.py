import os
import sys
import shutil
import subprocess
import datetime
import importlib.metadata

# Constants
CURR_DIR = os.path.dirname(os.path.abspath(__file__))
TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
EXP_DIR = CURR_DIR + f"_[{TIMESTAMP}]"
CODE_DIR = os.path.join(EXP_DIR, "Code")
RESULTS_DIR = os.path.join(EXP_DIR, "Results")
DATA_PATHS = {}

# Ensure output directories exist
def setup_experiment_directory():
    os.makedirs(EXP_DIR)
    os.makedirs(CODE_DIR)
    os.makedirs(RESULTS_DIR)

    # Copy all files from curr_dir to timestamped directory
    for item in os.listdir(CURR_DIR):
        src_path = os.path.join(CURR_DIR, item)
        dest_path = os.path.join(EXP_DIR, item)

        if os.path.isdir(src_path):
            shutil.copytree(src_path, dest_path)        
        elif os.path.isfile(src_path):
            shutil.copy(src_path, dest_path)

# Capture Python version, installed modules, Docker image, Slurm job info, and node name
def capture_environment_info():
    python_version = sys.version
    
    installed_packages = sorted([f"{dist.metadata['Name']}=={dist.version}" for dist in importlib.metadata.distributions()])
    slurm_job_id = os.getenv("SLURM_JOB_ID", "Not running under Slurm")
    node_name = os.getenv("SLURMD_NODENAME", os.uname().nodename)
    
    # Try to get Docker image name
    docker_image = "Unknown"
    try:
        container_id = subprocess.check_output("cat /etc/hostname", shell=True, stderr=subprocess.DEVNULL).decode().strip()
        docker_image = subprocess.check_output(f"docker inspect --format='{{{{.Config.Image}}}}' {container_id}", shell=True).decode().strip()
    except Exception:
        docker_image = "Could not retrieve Docker image"
    
    with open(os.path.join(CODE_DIR, "environment.txt"), "w") as f:
        f.write(f"Python Version:\n{python_version}\n\n")
        f.write(f"Docker Image: {docker_image}\n")
        f.write(f"Slurm Job ID: {slurm_job_id}\n")
        f.write(f"Node Name: {node_name}\n\n")
        f.write("Installed Packages:\n")
        f.write("\n".join(installed_packages))

# Copy external code and update search path
def copy_external_code():
    codepaths_file = os.path.join(CURR_DIR, "codepaths.txt")
    new_codepaths = []
    
    if os.path.exists(codepaths_file):
        with open(codepaths_file, "r") as f:
            for line in f:
                code_path = line.strip()
                if os.path.exists(code_path):
                    shutil.copytree(code_path, os.path.join(CODE_DIR, os.path.basename(code_path)), dirs_exist_ok=True)
                    new_codepaths.append(os.path.relpath(os.path.join(CODE_DIR, os.path.basename(code_path)), EXP_DIR))
    
    # Update codepaths.txt with relative paths
    with open(os.path.join(EXP_DIR, "codepaths.txt"), "w") as f:
        f.writelines("\n".join(new_codepaths) + "\n")

    # Add new code directory to search path
    sys.path.insert(0, CODE_DIR)

# Verify data paths and prepare arguments
def load_data_paths():
    global DATA_PATHS
    datapaths_file = os.path.join(CURR_DIR, "datapaths.txt")
    
    if os.path.exists(datapaths_file):
        with open(datapaths_file, "r") as f:
            for line in f:
                if "=" in line:
                    key, path = line.strip().split("=", 1)
                    if os.path.exists(path):
                        DATA_PATHS[key] = os.path.abspath(path)
                    else:
                        print(f"Warning: Data path does not exist: {path}")

# Load data paths at module import
load_data_paths()

def get_data_path(key):
    return DATA_PATHS.get(key, None)

def get_results_directory():
    return RESULTS_DIR

# Run main.py with verified paths
def run_experiment():
    main_script = os.path.join(EXP_DIR, "main.py")
    
    if not os.path.exists(main_script):
        raise FileNotFoundError("main.py not found in experiment directory")

    with open(os.path.join(RESULTS_DIR, "terminal_output.txt"), "w") as log_file:
        process = subprocess.Popen(["python3", main_script], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print(line, end='')  # Print to terminal
            log_file.write(line)  # Write to file
        process.stdout.close()
        process.wait()

# Create a new experiment folder structure
def initialize_experiment_folder():
    folder_path = CURR_DIR
    os.makedirs(folder_path, exist_ok=True)
    
    # Create empty main.py, codepaths.txt, and datapaths.txt
    open(os.path.join(folder_path, "main.py"), "w").close()
    open(os.path.join(folder_path, "codepaths.txt"), "w").close()
    open(os.path.join(folder_path, "datapaths.txt"), "w").close()
    
    print(f"Initialized experiment folder in: {folder_path}")

def start_experiment():
    # This function is specifically to allow calling this from within any script 
    # i.e., put logger.start_experiment() in any file and it should do its loggy thing
    
    setup_experiment_directory()
    capture_environment_info()
    copy_external_code()
    load_data_paths()
    run_experiment()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--initialize":
        initialize_experiment_folder()
    else:
        setup_experiment_directory()
        capture_environment_info()
        copy_external_code()
        run_experiment()
