import os, sys
import subprocess
import argparse
import datetime

parser = argparse.ArgumentParser()
parser.add_argument('--name', help='name of docker container', default="ml-hub")
parser.add_argument('--version', help='version tag of docker container', default="latest")
parser.add_argument('--deploy', help='deploy docker container to remote', action='store_true')

REMOTE_IMAGE_PREFIX = "mltooling/"

args, unknown = parser.parse_known_args()
if unknown:
    print("Unknown arguments "+str(unknown))

# Wrapper to print out command
def call(command):
    print("Executing: "+command)
    return subprocess.call(command, shell=True)

# calls build scripts in every module with same flags
def build(module="."):
    if not os.path.isdir(module):
        print("Could not find directory for " + module)
        sys.exit(1)

    build_command = "python build.py"
    
    if args.version:
        build_command += " --version=" + str(args.version)

    if args.deploy:
        build_command += " --deploy"

    working_dir = os.path.dirname(os.path.realpath(__file__))
    full_command = "cd " + module + " && " + build_command + " && cd " + working_dir
    print("Building " + module + " with: " + full_command)
    failed = call(full_command)
    if failed:
        print("Failed to build module " + module)
        sys.exit()

service_name = os.path.basename(os.path.dirname(os.path.realpath(__file__)))
if args.name:
    service_name = args.name

# docker build

# get git revision if possible
git_rev = "unknown"
try:
    git_rev = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode('ascii').strip()
except:
    pass

# get build timestamp
build_date = datetime.datetime.utcnow().isoformat("T") + "Z"
try:
    build_date = subprocess.check_output(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ']).decode('ascii').strip()
except:
    pass

vcs_ref_build_arg = " --build-arg ARG_VCS_REF=" + str(git_rev)
build_date_build_arg = " --build-arg ARG_BUILD_DATE=" + str(build_date)
version_build_arg = " --build-arg ARG_HUB_VERSION=" + str(args.version)

versioned_image = service_name+":"+str(args.version)
latest_image = service_name+":latest"
failed = call("docker build -t "+versioned_image+" -t "+latest_image + " " + vcs_ref_build_arg + " " + build_date_build_arg + " " + version_build_arg + " ./")

if failed:
    print("Failed to build container")
    sys.exit(1)

remote_versioned_image = REMOTE_IMAGE_PREFIX + versioned_image
call("docker tag " + versioned_image + " " + remote_versioned_image)

remote_latest_image = REMOTE_IMAGE_PREFIX + latest_image
call("docker tag " + latest_image + " " + remote_latest_image)

if args.deploy:
    call("docker push " + remote_versioned_image)

    if "SNAPSHOT" not in args.version:
    # do not push SNAPSHOT builds as latest version
        call("docker push " + remote_latest_image)

# Create the Helm chart resource
import fileinput

chart_yaml = "./helmchart/mlhub/Chart.yaml"
values_yaml = "./helmchart/mlhub/values.yaml"
with fileinput.FileInput(chart_yaml, inplace=True, backup='.bak') as file:
    for line in file:
        print(line.replace("$VERSION", str(args.version)), end='')

with fileinput.FileInput(values_yaml, inplace=True, backup='.bak') as file:
    for line in file:
        print(line.replace("$VERSION", str(args.version)), end='')

try:
    call("helm package ./helmchart/mlhub -d helmchart")
except:
    print("There was a problem with the helm command")

os.replace(f"{chart_yaml}.bak", chart_yaml)
os.replace(f"{values_yaml}.bak", values_yaml)
