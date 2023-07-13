# Python dependency list can be found in requirements.txt
import re
import sys
import gitlab
import os
import yaml
import base64
import json
import requests
from io import StringIO
from ruamel.yaml import YAML as RuamelYAML

class GitlabAPI():
    def __init__(self, token: str, url: str, proj_id: str):
        self.gitlab_access_token = token
        self.gitlab_url = url
        self.f5_project_id = proj_id
        self.gitl = gitlab.Gitlab(self.gitlab_url, self.gitlab_access_token)
        self.project = self.gitl.projects.get(self.f5_project_id)

    def get_job_trace(self, job_id: str) -> str:
        job = self.project.jobs.get(job_id, lazy=True)  #makes restapi object of job,,  lazy=True makes shallow object
        return job.trace()
    
def update_manifest(GITLAB_TOKEN: str, proj_id: str, branch_name: str, version: str, project_name: str) -> str:
    
    result = json.load(os.popen("curl --silent --header \"PRIVATE-TOKEN:{0}\" \
                              \"https://gitlab.com/api/v4/projects/{1}/repository/files/file-to-update.yaml?ref={2}\" ".format(GITLAB_TOKEN, proj_id, branch_name)))

    file = base64.b64decode(result["content"]).decode()
    data = yaml.safe_load(file)

    for artifact in data['artifacts']:
        if artifact['name'] == project_name:
            artifact['version'] = version.replace('"', "").strip()

    updated_content = StringIO()
    ruamel = RuamelYAML()
    ruamel.dump(data, updated_content)
    file = updated_content.getvalue()
    file = str(file.encode("utf-8"))
    file = file.replace("b'", "")
    file = file.replace("'", "")

    data = f"{{\"branch\": \"{branch_name}\",\"content\": \"{file}\",\"commit_message\": \"update input manifest\"}}"
    
    headers = {
        "PRIVATE-TOKEN":GITLAB_TOKEN, 
        "Content-Type":"application/json"
    }
    url = "https://gitlab.com/api/v4/projects/{0}/repository/files/file-to-update.yaml?ref={1}".format(proj_id, branch_name)
    server = requests.put(data=data, headers=headers, url=url)
    return server.text,server.status_code
    

# Make function to parse job to grab  version from myproject
# This can use the GitlabAPI class since it's hosted on gitswarm
def get_version(gl: GitlabAPI) -> str:
    # get completed successfull pipeline for a branch 
    pipelines = gl.project.pipelines.list(ref="releaseBranch",status="success",scope="finished",get_all=True)
    latest_pipeline_id = pipelines[0].id
    pipeline = gl.project.pipelines.get(latest_pipeline_id)
    jobs = pipeline.jobs.list()
    for job in jobs:
        if "helm-publish" == job.name:
            job_id = job.id
    trace = gl.get_job_trace(job_id)

    trace_string = trace.decode('utf8')
    # Extract version as expressed by --version value
    extractVersion = re.findall(r'--version(.*) --app-version', trace_string)
    return extractVersion[0]

if __name__ == "__main__":
    
    GITLAB_TOKEN=os.environ["GITLAB_TOKEN"]
    URL = 'https://gitlab.com'  
    PROJ_ID = 1010 # bigcne projectID
   
    
    # Arguments expects branch name
    if len(sys.argv) != 2 :
        print("Branch name was not passed as an argument")
        exit(1)
    else:
       Branch=sys.argv[1]
    
    gl = GitlabAPI(GITLAB_TOKEN, URL, PROJ_ID)

   Version=get_version(gl)
   
    print("Manifest update for project {} on branch {}".format(PROJ_ID,Branch))
    output,statuscode= update_manifest(GITLAB_TOKEN, PROJ_ID, Branch , version , "repoprojectname")
    if statuscode !=200:
        print("Manifest update has FAILED for project {} on branch {}".format(PROJ_ID,Branch))
    else:
        print("Manifest update is SUCCESSFUL for project {} on branch {} with version {}".format(PROJ_ID,Branch,version))
