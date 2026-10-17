#this file determines the content of the app
#views are the code you write to respond to requests to your application
#The view returns data that Flask turns into an outgoing response.

from flask import render_template
from HelloFlask import app

@app.route('/')
@app.route('/home')
def home():
        return render_template(
        "index.html"
        )