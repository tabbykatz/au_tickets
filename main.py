#===          Import packages      ===#
from flask import Blueprint, render_template, flash
from flask_login import login_required, current_user
from __init__ import create_app, db

# main blueprint
main = Blueprint('main', __name__)

@main.route('/') # home page
def index():
    return render_template('index.html')

@main.route('/profile') # profile page
@login_required
def profile():
    return render_template('profile.html', name=current_user.name)

app = create_app() # initialize app using __init__.py
if __name__ == '__main__':
    db.create_all(app=create_app()) # create SQLite db
    app.run(debug=True) # run the flask app debug mode
