import datetime as dt
import numpy as np
import pandas as pd
import re
import requests
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Microsoft Graph API - SharePoint Client
class spClient:

    def __init__(self):
        self.tenant_id = "YYY"
        self.client_id = "ZZZ"
        self.client_secret = "XXX"
        self.grant_type = "client_credentials"
        self.resource_url = "https://graph.microsoft.com/"
        self.base_url = self.resource_url + "v1.0/"
        self.login_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/token"
        self.api_headers = {"Content-Type": "application/x-www-form-urlencoded"}

        self.site_root = "one.aon.net"
        self.site_main = "RetirementInvestment-ACIASG"
        self.folder = "Documents"
        self.access_token = self.get_access_token()
        self.auth_headers = {"Authorization": f"Bearer {self.access_token}"}
        self.upload_headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/octet-stream"
        }
        self.site_id = self.get_site_id()
        self.drive_id = self.get_drive_id()

    def get_access_token(self):
        body = {
            "grant_type": self.grant_type,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "resource": self.resource_url 
            }
        response = requests.get(self.login_url, headers=self.api_headers, data=body)
        return response.json().get("access_token")
    
    def get_site_id(self):
        url = self.base_url + f"sites/{self.site_root}:/sites/{self.site_main}"
        return self._get(url, key="id").split(",")[1]
    
    def get_drive_id(self):
        url = self.base_url + f"sites/{self.site_root}:/sites/{self.site_main}:/drives"
        drives = self._get(url)
        return [drive.get("id") for drive in drives if drive.get("name") == self.folder][0]

    def get_files(self, sp_rpath):
        url = self.base_url + f"drives/{self.drive_id}/root:/{sp_rpath}:/children"
        files = self._get(url)
        return [file.get("name") for file in files if re.search(r"\.[a-z]{,4}", file.get("name"))]
    
    def get_latest_file(self, sp_rpath):
        url = self.base_url + f"drives/{self.drive_id}/root:/{sp_rpath}:/children"
        files = self._get(url)
        latest_ts = max([dt.datetime.strptime(file.get("createdDateTime"), "%Y-%m-%dT%H:%M:%SZ") for file in files])
        return [file.get("name") for file in files 
                if (
                    re.search(r"\.[a-z]{,4}", file.get("name")) and \
                    file.get("createdDateTime") == latest_ts.strftime("%Y-%m-%dT%H:%M:%SZ")
                    )]

    def download_files(self, sp_rpath, dbfs_path, get_fnames=True, sp_fpath=[]):
        if get_fnames:
            files = self.get_files(sp_rpath)
        else:
            files = [path.split("/")[-1] for path in sp_fpath]
        if len(files) == 0:
            raise Exception(f"No files found in {self.folder}/{sp_rpath}. Please check and provide the correct SharePoint relative path!")
        else:
            for idx, file in enumerate(files):
                if get_fnames:
                    url = self.base_url + f"drives/{self.drive_id}/root:/{sp_rpath}/{file}:/content"
                else:
                    url = self.base_url + f"drives/{self.drive_id}/root:/{sp_fpath[idx]}:/content"
                response = requests.get(url, headers=self.auth_headers, verify=False)
                if response.status_code == 200:
                    with open(dbfs_path + '/' + file, "wb") as f:
                        f.write(response.content)
                    print("{0} is downloaded successfully in {1}".format(file, dbfs_path))
                else:
                    response.raise_for_status()
        
    def upload_files(self, sp_rpath, file_paths=[]):
        if len(file_paths) == 0:
            print("No filepaths provided!")
        else:
            for file_path in file_paths:
                file = file_path.split("/")[-1]
                url = self.base_url + f"sites/{self.site_id}/drives/{self.drive_id}/items/root:/{sp_rpath}/{file}:/content"
                with open(file_path, "rb") as f:
                    requests.put(url, headers=self.upload_headers, data=f)
                print("{0} is uploaded successfully in {1}".format(file, sp_rpath))

    def copy_files(self, source_paths=[], dest_rpaths=[], delete_source=False):
        if len(source_paths) != len(dest_rpaths):
            raise("The size of source and destination paths are not the same!")
        else:
            for idx, source_path in enumerate(source_paths):
                source_url = self.base_url + f"drives/{self.drive_id}/root:/{source_path}:/content"
                response = requests.get(source_url, headers=self.auth_headers, verify=False)
                if response.status_code == 200:
                    dest_url = self.base_url + f"sites/{self.site_id}/drives/{self.drive_id}/items/root:/{dest_rpaths[idx]}:/content"
                    requests.put(dest_url, headers=self.upload_headers, data=response.content)
                    if delete_source:
                        file_id = self._get(source_url.split(":/content")[0], key="id")
                        requests.delete(self.base_url + f"sites/{self.site_id}/drives/{self.drive_id}/items/{file_id}", headers=self.auth_headers,)
                        action = "moved"
                    else:
                        action = "copied"
                    print("{0} is {1} successfully into {2}".format(source_path.split("/")[-1], action, "/".join(dest_rpaths[idx].split("/")[:-1])))

    def _get(self, url, key="value"):
        response = requests.get(url, headers=self.auth_headers)
        if key == "value":
            return response.json().get(key, [])
        elif key == "id":
            return response.json().get(key)
        else:
            raise("Given ID is not recognized!")