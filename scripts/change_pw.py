import os
import requests

url = "http://localhost:9000/api/users/change_password"
data = {
    "login": os.getenv("SONAR_USER", "admin"),
    "previousPassword": os.getenv("SONAR_OLD_PASSWORD", ""),
    "password": os.getenv("SONAR_NEW_PASSWORD", "")
}
auth = (os.getenv("SONAR_USER", "admin"), os.getenv("SONAR_OLD_PASSWORD", ""))

try:
    response = requests.post(url, data=data, auth=auth)
    print("Status:", response.status_code)
    print("Response:", response.text)
except Exception as e:
    print("Error:", e)
