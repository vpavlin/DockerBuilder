from flask import render_template
from app import app
import os
import requests
import json
import datetime
from DepViewer import DepViewer

registry_path = "/var/lib/docker-registry/"

@app.route('/')
@app.route('/index')
def index():

    dv = DepViewer(True)
    images = json.dumps(dv.getDepsList("48d5ee42eeca"))
    return render_template("index.html", images = images , title = "Dependency View")
