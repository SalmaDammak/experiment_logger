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
    main_script_py = os.path.join(EXP_DIR, "main.py")
    main_script_sh = os.path.join(EXP_DIR, "main.sh")
    
    if not os.path.exists(main_script_py) and not os.path.exists(main_script_sh):
        raise FileNotFoundError("Neither main.py nor main.sh found in experiment directory, please provide one.")
    
    if os.path.exists(main_script_py) and os.path.exists(main_script_sh):
        print("WARNING: Both main.py and main.sh found in experiment directory. Running main.sh.")
    
    if os.path.exists(main_script_sh):
        script_path = main_script_sh
    else:
        script_path = main_script_py
    
    with open(os.path.join(RESULTS_DIR, "terminal_output.txt"), "w") as log_file:
        if script_path.endswith(".sh"):
            process = subprocess.Popen(["sh", script_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        else:
            process = subprocess.Popen(["python3", script_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        for line in process.stdout:
            print(line, end='')  # Print to terminal
            log_file.write(line)  # Write to file
        process.stdout.close()
        process.wait()

# Create a new experiment folder structure
def initialize_experiment_folder():
    folder_path = CURR_DIR
    os.makedirs(folder_path, exist_ok=True)
    
    # Create empty main.py, main.sh, codepaths.txt, and datapaths.txt
    open(os.path.join(folder_path, "main.py"), "w").close()
    open(os.path.join(folder_path, "main.sh"), "w").close()
    open(os.path.join(folder_path, "codepaths.txt"), "w").close()
    open(os.path.join(folder_path, "datapaths.txt"), "w").close()
    
    print(f"Initialized experiment folder in: {folder_path}")

# ======================================================================================
# Within .py script usage: put "logger.start_experiment()"
# in any file and it will do the same thing as running it from terminal.
# ======================================================================================
class Tee:
    def __init__(self, *files):
        self.files = files

    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush()  # Ensure the output is written immediately

    def flush(self):
        for f in self.files:
            f.flush()

def log_terminal():
    # Log terminal output to a file
    with open(os.path.join(RESULTS_DIR, "terminal_output.txt"), "w") as log_file:
        sys.stdout = Tee(sys.stdout, log_file)
        sys.stderr = Tee(sys.stderr, log_file)

def start_experiment():
    setup_experiment_directory()
    capture_environment_info()
    copy_external_code()
    load_data_paths()
    log_terminal()

# ======================================================================================
# Terminal usage: to be called in terminal as "python3 logger.py" where it will run 
# main.sh (default if present) or main.py.
# ======================================================================================

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--initialize":
        initialize_experiment_folder()
    else:
        setup_experiment_directory()
        capture_environment_info()
        copy_external_code()
        run_experiment()
